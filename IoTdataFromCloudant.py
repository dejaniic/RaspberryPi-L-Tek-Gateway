# Imports
from cloudant import cloudant
from cloudant.result import Result, ResultByKey
import csv
import json
import sys

# Prerequsites
#   1) Install python
#   2) Install pip
# Before first usage:
#   1) Open terminal
#   2) Run: pip install cloudant
#       (https://github.com/cloudant/python-cloudant#installation-and-usage)
# Running this script
#   1) Open terminal
#   2.1) python all_participants.py
#   or
#   2.2) python3 all_participants.py

# Settings (copy from CLoudant Service Credentials on IBM Cloud)
USERNAME = "<username>-bluemix"
PASSWORD = "<password>"
URL = "https://<cloudant-id>-bluemix.cloudant.com"
DATABASE_NAME = "<db-name>"
csvfile = "iotdata.csv"


# Check version
try:
    assert sys.version_info >= (3, 0)
except:
    print("-------------------- WARNING --------------------")
    print("Please install python version 3 or above.")
    print("Version 2.7 might chrash.")
    print("Current version:")
    print(sys.version)
    print("-------------------------------------------------")
# ---------------------------------------------------------------------------- #


print("Connecting to database...")
with cloudant(user=USERNAME, passwd=PASSWORD, url=URL) as client:
    print("List of all databases: ", client.all_dbs())
    print("Connecting to : " + DATABASE_NAME)
    database = client[DATABASE_NAME]
    print("Gathering data...")
    result_collection = Result(database.all_docs, include_docs=True)
    print("Generating csv file...")

    # Open csv file with write permission
    with open(csvfile, "w") as output:
        number_of_rows = 0
        # Create cvs writer
        writer = csv.writer(output, lineterminator='\n')
        # Write rows to csv file
        for result in result_collection:
            # get data from collection
            data = json.dumps([result['doc']][0])

            # Write header
            if number_of_rows == 0:
                out = json.loads(data)
                header = list(out["d"].keys())
                writer.writerow(header)

            # Get data
            out = json.loads(data)

            row = []
            for i, d in enumerate(out.values()):
                if i == 2:
                    for el in list(d.values()):
                        row.append(el)

            writer.writerow(row)
            number_of_rows += 1

    print("Created file:", csvfile)
