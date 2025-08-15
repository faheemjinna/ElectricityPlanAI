from playwright.sync_api import sync_playwright
import os
import mysql.connector
import logging
import shutil
import fitz
from geminiResponse import geminiResponseGenerator
import formulaLogic
from dbConfigDetails import DB_CONFIG
from dotenv import load_dotenv
import shutil
import mysql.connector  # Ensure your DB imports are at the top
from openpyxl import Workbook
from openpyxl.styles import Font
from flask import jsonify

load_dotenv()

# DB_Connection
mydb = mysql.connector.connect(**DB_CONFIG)
mycursor = mydb.cursor(dictionary=True)

# Folders
downloadsFolder = "downloads"
calculatedFolder = "calculated"
textOutputFolder = "extracted_texts"
base_folder = os.path.dirname(__file__)
download_folder = os.path.join(base_folder, "downloads")
calculated_folder = os.path.join(base_folder, "calculated")
sheet_folder = os.path.join(base_folder, "sheets")

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
    
    response_json = geminiResponseGenerator(textFileName)
    
    # print(f"Response JSON: {response_json}")
    
   # Validate and extract expected fields
    companyName = response_json.get("company_name", "")
    baseCharge = float(response_json.get("base_price", 0.0))
    tiers = response_json.get("tiers", [])
    description = response_json.get("description", "")
    
    return companyName, baseCharge, tiers

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

def storePlanDetails(planid, companyid, planName, typeInput):
    try:
        # Check for existing record with same plan name, company ID, and type
        mycursor.execute("""
            SELECT id FROM plan_details
            WHERE plan_name = %s AND companyID = %s AND type = %s
        """, (planName, companyid, typeInput))
        result = mycursor.fetchone()

        if result:
            # Record exists — update with new planID
            mycursor.execute("""
                UPDATE plan_details
                SET planID = %s
                WHERE id = %s
            """, (planid, result['id']))
            print(f"✅ Updated existing plan detail (ID: {result['id']}) with new planID {planid}")
        else:
            # Insert new record
            mycursor.execute("""
                INSERT INTO plan_details (planID, plan_name, companyID, type)
                VALUES (%s, %s, %s, %s)
            """, (planid, planName, companyid, typeInput))
            print(f"✅ Inserted new plan details for planID {planid}")

        mydb.commit()

    except mysql.connector.Error as err:
        print(f"❌ Failed to store plan details: {err}")

def getProviderLinks(typeInput, companyInput):
    try:
        query = """
            SELECT p.companyID, p.companyName, p.dataLink, p.type
            FROM providers p
            JOIN company c ON p.companyName = c.companyName
            WHERE p.dataLink IS NOT NULL
              AND p.type = %s
              AND c.companyid = %s
        """
        mycursor.execute(query, (typeInput, companyInput))
        providers = mycursor.fetchall()
        return providers

    except mysql.connector.Error as err:
        print(f"Database connection failed: {err}")
        raise

def fetch_and_download_pdfs(download_dir, typeInput, companyInput):
    providers = getProviderLinks(typeInput, companyInput)
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

def fetchLatestData(typeInput, companyInput):
    # Step 2: Setup folders
    os.makedirs(calculated_folder, exist_ok=True)
    os.makedirs(sheet_folder, exist_ok=True)

    # Step 3: Fetch files
    downloaded_files = fetch_and_download_pdfs(download_folder, typeInput, companyInput)

    # plan_data = {}  # key = planName, value = [month1_estimate, month2_estimate, ..., month12_estimate]

    for file_info in downloaded_files:
        planName = file_info['planName']
        companyName = file_info['companyName']
        pdfPath = file_info['path']
        filename = os.path.basename(pdfPath)

        try:
            company, base, tiers = extractPlanDetails(pdfPath)
            formula = formulaLogic.buildFormulaString(base, tiers)

            # Store to DB
            planid = getOrCreatePlan(company, base, formula, tiers)
            if planid:
                mycursor.execute("SELECT companyid FROM company WHERE companyname = %s", (company,))
                result = mycursor.fetchone()
                if result:
                    companyid = result['companyid']
                    storePlanDetails(planid, companyid, planName, typeInput)

            # Move PDF to calculated/
            dest_path = os.path.join(calculated_folder, filename)
            shutil.move(pdfPath, dest_path)

        except Exception as e:
            print(f"Error processing {filename}: {e}")
            
def processEnergyEstimates(typeInput, companyInput, usage_kwh, loadLatest):
    
    plan_data = {}  # key = planName, value = [month1_estimate, month2_estimate, ..., month12_estimate]
    
    if loadLatest:
        fetchLatestData(plan_data)
    else:
        mycursor.execute("""
    SELECT 
        c.companyname, 
        p.planID, 
        p.baseAmount, 
        p.formula, 
        pd.plan_name
    FROM electricity_plans.plan_details pd
    JOIN electricity_plans.company c 
        ON pd.companyID = c.companyid
    JOIN electricity_plans.plans p 
        ON p.planID = pd.planID
    WHERE pd.type = %s
      AND pd.companyID = %s
    GROUP BY p.planID
""", (typeInput, companyInput))
        rows = mycursor.fetchall()
        for row in rows:
            planName = row['plan_name']
            baseAmount = float(row['baseAmount'])
            formula = row['formula']
            print(f"Processing plan: {planName}, Base Amount: {baseAmount}, Formula: {formula}")

            monthly_estimates = []
            for usage in usage_kwh:
                estimated_bill = formulaLogic.evaluateFormula(float(usage), baseAmount, formula)
                monthly_estimates.append(round(estimated_bill, 2))

            plan_data[planName] = monthly_estimates
            
    # Build structured response
    plans_list = []

    for plan_full_name, monthly_costs in plan_data.items():
        # Split into company and plan name
        plan_info = {
            "company": companyInput,
            "plan_name": plan_full_name,
            # "usage_kwh": usage_kwh,
            # "months": [
            #     {"month": f"Month {i+1}", "amount": monthly_costs[i]}
            #     for i in range(len(monthly_costs))
            # ],
            "total": round(sum(monthly_costs), 2)
        }
        plans_list.append(plan_info)

    return jsonify({
        "status": "success",
        "plans": plans_list
    })

# def setUserData(typeInput, companyInput, loadLatest, usageInputArray):
    # typeInput = "apartment"  # Example input
    # companyInput = 2  # Example company ID
    # loadLatest = True  # Example flag to load latest data
    # usageInputArray = [100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650]  # Example usage for 12 months
    
if __name__ == "__main__":
    # Step 1: Get user input
    # typeInput = input("Enter type (e.g., apartment): ").strip()
    # companyInput = int(input("Enter company ID: "))

    # usageInputArray = []
    # for i in range(1, 13):
    #     usage = float(input(f"Enter usage for month {i} (kWh): "))
    #     usageInputArray.append(usage)

    typeInput = "apartment"  # Example input
    companyInput = 2  # Example company ID
    loadLatest = False  # Example flag to load latest data
    usageInputArray = [100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650]  # Example usage for 12 months
    processEnergyEstimates(typeInput, companyInput, usageInputArray, loadLatest)
    print("\n✅ Processing complete.") 