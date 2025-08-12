from flask import Flask
from flask_restful import Api, Resource, reqparse, abort, fields, marshal_with
import mysql.connector
from sql_config import DB_CONFIG
from datetime import datetime

app = Flask(__name__)
api = Api(app)

# DB Connection
mydb = mysql.connector.connect(**DB_CONFIG)
mycursor = mydb.cursor(dictionary=True)

# Argument parser for POST/PUT if needed
user_args = reqparse.RequestParser()
user_args.add_argument('name', type=str, required=True, help='Name cannot be blank')
user_args.add_argument('email', type=str, required=True, help='Email cannot be blank')

# Helper to serialize datetime
def serialize_result(rows):
    for row in rows:
        for key, value in row.items():
            if isinstance(value, datetime):
                row[key] = value.isoformat()
    return rows

class ProviderList(Resource):
    def get(self):
        try:
            query = "SELECT * FROM providers"
            mycursor.execute(query)
            result = mycursor.fetchall()
            result = serialize_result(result)
            return {'providers': result}, 200
        except Exception as e:
            return {'error': str(e)}, 500

api.add_resource(ProviderList, "/providers")

@app.route('/')
def home():
    return "<h1>Hello, World!</h1>"

if __name__ == '__main__':
    app.run(debug=True)