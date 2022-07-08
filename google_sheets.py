from __future__ import print_function
import httplib2

from apiclient import discovery

import api_key


def get_sheet_data(id, range):
    discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?'
                    'version=v4')
    service = discovery.build(
        'sheets',
        'v4',
        http=httplib2.Http(),
        discoveryServiceUrl=discoveryUrl,
        developerKey=api_key.google_sheets_key)

    spreadsheetId = id
    rangeName = range
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheetId, range=rangeName).execute()
    return result.get('values', [])



#get_sheet_data('1a7cPSN1AcHaYidhNCiaDmJRWqFKLZdKP56PrefOBIhg', 'Live Order Update from the E-Store!A1:J')