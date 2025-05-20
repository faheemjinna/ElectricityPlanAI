from playwright.sync_api import sync_playwright
import os
import mysql.connector
import logging
import shutil
import fitz
import re
from sql_config import DB_CONFIG

# DB_Connection
mydb = mysql.connector.connect(**DB_CONFIG)
mycursor = mydb.cursor(dictionary=True)

# Folders
downloadsFolder = "downloads"
calculatedFolder = "calculated"
textOutputFolder = "extracted_texts"
os.makedirs(downloadsFolder, exist_ok=True)
os.makedirs(textOutputFolder, exist_ok=True)
os.makedirs(calculatedFolder, exist_ok=True)

def extractPlanDetails(pdfPath):
    documentData = fitz.open(pdfPath)
    fullPageText = ""
    for page in documentData:
        fullPageText += page.get_text()
    
    #Writing the full text to a file
    textFileName = os.path.join(textOutputFolder, os.path.splitext(os.path.basename(pdfPath))[0] + ".txt")
    with open(textFileName, "w", encoding="utf-8") as f:
        f.write(fullPageText)
    
    lines = fullPageText.split('\n')
    
    # Extract company name
    # Assuming the company name is the first non-empty line after "Electricity Facts Label"
    companyName = None
    for i, line in enumerate(lines):
        if "Electricity Facts Label" in line:
            for j in range(i + 1, len(lines)):
                if lines[j].strip():
                    companyName = lines[j].strip()
                    break
            break

    baseCharge = 0.0
    baseChargePattern = re.compile(r'Base Charge:.*?\$?(\d+\.\d{2})', re.IGNORECASE | re.DOTALL)
    baseChargeMatch = baseChargePattern.search(fullPageText)
    if baseChargeMatch:
        baseCharge = float(baseChargeMatch.group(1)) # Extract base charge from first group regex match
    else:
        for i, line in enumerate(lines):
            if "Base Charge" in line:
                for j in range(i + 1, len(lines)):
                    amountMatch = re.search(r'\$?(\d+\.\d{2})', lines[j])
                    if amountMatch:
                        baseCharge = float(amountMatch.group(1))
                        break
                break

    # creditMatch = re.search(r'Usage Credit.*?\$([\d.]+).*?when usage is (?:above or equal to|>=)\s*(\d+)', fullPageText, re.IGNORECASE)
    # usageCredit = None
    # if creditMatch:
    #     usageCredit = {
    #         'amount': float(creditMatch.group(1)),
    #         'threshold': int(creditMatch.group(2))
    #     }

    tierMatches = re.findall(r'(?:All\s*kWh|(?:(\d+)\s*-\s*(\d+)|>\s*(\d+))\s*kWh)\s+([\d.]+)¢', fullPageText)
    tiers = []
    for m in tierMatches:
        if m[0] and m[1]:
            tiers.append({'min': int(m[0]), 'max': int(m[1]), 'rate': float(m[3])})
        elif m[2]:
            tiers.append({'min': int(m[2]) + 1, 'max': None, 'rate': float(m[3])})
        else:
            tiers.append({'min': 0, 'max': None, 'rate': float(m[3])})

    return companyName, baseCharge, tiers

def buildFormulaString(baseCharge, tiers):
    formula = f"base"
    for tier in tiers:
        if tier['max'] is not None:
            # usage = 600
            #0-500 base + min(usage - 0, 500) * rate
            formula += f" + min(max(usage - {tier['min'] - 1}, 0), {tier['max'] - tier['min'] + 1}) * {tier['rate']}"
        else:
            formula += f" + max(usage - {tier['min'] - 1}, 0) * {tier['rate']}"
    return f"({formula}) / 100"

def evaluateFormula(usage_kwh, baseCharge, formula_str):
    localVariables = {'usage': usage_kwh, 'base': baseCharge*100, 'min': min, 'max': max}
    return round(eval(formula_str, {}, localVariables), 2)

def getOrCreatePlan(company, base, formula, tiers):
    # Get existing plan ID or create new one if doesn't exist
    # Get company id
    mycursor.execute("SELECT companyid FROM company WHERE companyname = %s", (company,))
    result = mycursor.fetchone()
    if not result:
        print(f"Company '{company}' not found in the company table.")
        return None
    companyid = result['companyid']

    # Check for existing plan
    mycursor.execute("SELECT planid FROM plans WHERE companyid = %s AND formula = %s", (companyid, formula))
    existingPlan = mycursor.fetchone()
    
    if existingPlan:
        print("Using existing plan.")
        return existingPlan['planid']
    else:
        # Insert new plan
        tierCount = len(tiers)
        mycursor.execute("""
            INSERT INTO plans (baseAmount, formula, tierCount, description, companyid)
            VALUES (%s, %s, %s, %s, %s)
        """, (base, formula, tierCount, '', companyid))
        planid = mycursor.lastrowid

        # Insert tiers
        for tier in tiers:
            mycursor.execute("""
                INSERT INTO tiers (planID, min, max, rate)
                VALUES (%s, %s, %s, %s)
            """, (planid, tier['min'], tier['max'], tier['rate']))

        mydb.commit()
        print(f"Created new plan. Plan ID: {planid}")
        return planid

def storePlanDetails(planid, companyid, planName, pdf_filename):
    # Store plan_details in the database
    try:
        mycursor.execute("""
            INSERT INTO plan_details (planID, plan_name, companyID)
            VALUES (%s, %s, %s)
        """, (planid, planName, companyid))
        mydb.commit()
        print(f"Stored plan details for plan ID {planid}")
    except mysql.connector.Error as err:
        print(f"Failed to store plan details: {err}")

def getProviderLinks():
    try:
        query = "SELECT companyID, companyName, dataLink, type FROM providers WHERE dataLink IS NOT NULL"
        mycursor.execute(query)
        providers = mycursor.fetchall()       
        return providers
        
    except mysql.connector.Error as err:
        print(f"Database connection failed: {err}")
        raise

def fetch_and_download_pdfs(download_dir):
    providers = getProviderLinks()
    if not providers:
        print("No providers with data links found in database")
        return []

    downloaded_files = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            accept_downloads=True,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )

        for provider in providers:
            url = provider['dataLink']
            print(f"Processing URL: {url}")
            companyName = provider['companyName'].replace(" ", "_")
            providerType = provider['type']
            company_id = provider['companyID'] #might need to get from company table
            
            try:
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)

                pdfLinks = page.query_selector_all('button.rvPlanButton, a[href*="formType=EnergyFactsLabel"]')
                
                #look for it
                
                seenLinks = set()
                planName = None
                
                for i, link_el in enumerate(pdfLinks, 1):
                    href = link_el.get_attribute("href")
                    if link_el.get_attribute("data-planname") != None:
                        planName = (link_el.get_attribute("data-planname"))
                    if not href or href in seenLinks:
                        continue
                    seenLinks.add(href)
                    print(f"\nFound link: {href} \Company Name: {companyName} \nPlan Name: {planName}")

                    filename = f"{companyName}_{providerType}_{i}.pdf" #insted could use numberic increase
                    save_path = os.path.join(download_dir, filename)

                    try:
                        new_page = context.new_page()
                        new_page.goto(href)
                        
                        with new_page.expect_download() as download_info:
                            new_page.wait_for_timeout(2000)

                        download = download_info.value
                        download.save_as(save_path)
                        
                        logging.info(f"Downloaded: {filename} from {href}")
                        downloaded_files.append({
                            'path': save_path,
                            'planName': planName,
                            'companyName': provider['companyName']  # Original company name
                        })
                        new_page.close()

                    except Exception as e:
                        logging.error(f"Failed to download PDF {i} from {companyName}: {e}")

                page.close()

            except Exception as e:
                logging.error(f"Failed to process {companyName} ({url}): {e}")

        browser.close()
        return downloaded_files


if __name__ == "__main__":
    download_folder = os.path.join(os.path.dirname(__file__), "downloads")
    downloaded_files = fetch_and_download_pdfs(download_folder)
    usage_kwh = 397

    for file_info in downloaded_files:
        pdfPath = file_info['path']
        planName = file_info['planName']
        companyName = file_info['companyName']
        filename = os.path.basename(pdfPath)
        
        try:
            company, base, tiers = extractPlanDetails(pdfPath)
            formula = buildFormulaString(base, tiers)
            estimated_bill = evaluateFormula(usage_kwh, base, formula)
            avg_rate = round((estimated_bill / usage_kwh) * 100, 2)

            print(f"\nProcessing: {filename}")
            print(f"Company: {company}")
            print(f"Plan Name: {planName}")
            print(f"Base Charge: ${base}")
            print(f"Tiers: {tiers}")
            print(f"Formula: {formula}")
            print(f"Estimated Bill for {usage_kwh} kWh: ${estimated_bill}")
            print(f"Average Rate: {avg_rate}¢/kWh")

            # Get or create plan and get plan ID
            planid = getOrCreatePlan(company, base, formula, tiers)
            
            if planid:
                # Get company ID
                mycursor.execute("SELECT companyid FROM company WHERE companyname = %s", (company,))
                company_result = mycursor.fetchone()
                if company_result:
                    companyid = company_result['companyid']
                    # Store plan details
                    storePlanDetails(planid, companyid, planName, filename)
                else:
                    print(f"Company not found: {company}")

            # Move processed file
            dest_path = os.path.join(calculatedFolder, filename)
            shutil.move(pdfPath, dest_path)
            print(f"Moved to: {dest_path}")

        except Exception as e:
            print(f"Error processing {filename}: {e}")

    mycursor.close()
    mydb.close()