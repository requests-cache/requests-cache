from mongita import MongitaClientDisk
from pymongo import MongoClient


def test_ids(client):
    collection = client['test_db']['test_collection']
    collection.replace_one(
        {'_id': 'id_from_filter'},
        replacement={'key': 'value'},
        upsert=True,
    )
    doc = collection.find_one({'_id': 'id_from_filter'})
    print(f'Fetched document by ID: {doc}')

    print('All IDs:')
    for d in collection.find({}):
        print(d['_id'])


print('pymongo\n----------')
test_ids(MongoClient())

print('\nmongita\n----------')
test_ids(MongitaClientDisk())
