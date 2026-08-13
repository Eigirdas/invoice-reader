
import os

from apiclient import discovery
from google.oauth2 import service_account

def append_to_sheets(sorted_json):
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive.file"]
        secret_file = os.path.join(os.getcwd(),'invoice_secret.json')

        spreadsheet_id = '1imeiAjD-WaQgzeJLFYVQW4lkAydD5kgtPTQE14ZeR-Y'
        range_name = 'Lapas1!A:E'

        credentials = service_account.Credentials.from_service_account_file(secret_file, scopes = scopes)
        service = discovery.build('sheets','v4',credentials=credentials)

        values = []
        for rows in sorted_json:
            values.append([
                rows['date'],
                rows['seller'],
                rows['price_excl_vat'],
                rows['vat'],
                rows['price_incl_vat'],
            ])


        data = {
            'values' : values 
        }

        service.spreadsheets().values().append(spreadsheetId=spreadsheet_id, body=data, range=range_name, valueInputOption='USER_ENTERED').execute()



    except OSError as e:
        print (e)



