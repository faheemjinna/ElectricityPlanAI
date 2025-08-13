from flask import Flask, jsonify, request
import mysql.connector  # Ensure your DB imports are at the top
import planFinalCodeUpdated
from dbConfigDetails import DB_CONFIG

app = Flask(__name__)

# DB_Connection
mydb = mysql.connector.connect(**DB_CONFIG)
mycursor = mydb.cursor(dictionary=True)

#Routes
@app.route('/')
def home():
    return "Welcome to the Electricity Plan AI"

@app.route('/about')
def about():
    return "About the Electricity Plan AI"

@app.route('/company', methods=['GET'])
def get_companies():
    try:
        mycursor.execute("SELECT * FROM company")
        result = mycursor.fetchall()
        return jsonify(result)
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500

@app.route('/company/<int:company_id>', methods=['GET'])
def get_company(company_id):
    try:
        mycursor.execute("SELECT * FROM company WHERE companyid = %s", (company_id,))
        result = mycursor.fetchall()
        return jsonify(result)
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 404

@app.route('/updatedata', methods=['POST'])
def updatedata():
    try:
        typeInput = request.args.get('type_input')
        companyInput = request.args.get('company_input')
        planFinalCodeUpdated.fetchLatestData(typeInput, companyInput)  # Call the function
        return jsonify({"message": "Task completed successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)