#!/usr/bin/env python
# -*- coding: utf-8 -*-
import xml.etree.cElementTree as ET
import pprint
import re
import codecs
import json
import os
"""
Your task is to wrangle the data and transform the shape of the data
into the model we mentioned earlier. The output should be a list of dictionaries
that look like this:

{
"id": "2406124091",
"type: "node",
"visible":"true",
"created": {
          "version":"2",
          "changeset":"17206049",
          "timestamp":"2013-08-03T16:43:42Z",
          "user":"linuxUser16",
          "uid":"1219059"
        },
"pos": [41.9757030, -87.6921867],
"address": {
          "housenumber": "5157",
          "postcode": "60625",
          "street": "North Lincoln Ave"
        },
"amenity": "restaurant",
"cuisine": "mexican",
"name": "La Cabana De Don Luis",
"phone": "1 (773)-271-5176"
}

You have to complete the function 'shape_element'.
We have provided a function that will parse the map file, and call the function 
with the element as an argument. You should return a dictionary, containing the 
shaped data for that element.
We have also provided a way to save the data in a file, so that you could use
mongoimport later on to import the shaped data into MongoDB. 

Note that in this exercise we do not use the 'update street name' procedures
you worked on in the previous exercise. If you are using this code in your final
project, you are strongly encouraged to use the code from previous exercise to 
update the street names before you save them to JSON. 

In particular the following things should be done:
- you should process only 2 types of top level tags: "node" and "way"
- all attributes of "node" and "way" should be turned into regular key/value pairs, except:
    - attributes in the CREATED array should be added under a key "created"
    - attributes for latitude and longitude should be added to a "pos" array,
      for use in geospacial indexing. Make sure the values inside "pos" array are floats
      and not strings. 
- if the second level tag "k" value contains problematic characters, it should be ignored
- if the second level tag "k" value starts with "addr:", it should be added to a 
  dictionary "address"
- if the second level tag "k" value does not start with "addr:", but contains ":", 
  you can process it in a way that you feel is best. For example, you might split it into
   a two-level dictionary like with "addr:", or otherwise convert the ":" to create a 
   valid key.
- if there is a second ":" that separates the type/direction of a street,
  the tag should be ignored, for example:

<tag k="addr:housenumber" v="5158"/>
<tag k="addr:street" v="North Lincoln Avenue"/>
<tag k="addr:street:name" v="Lincoln"/>
<tag k="addr:street:prefix" v="North"/>
<tag k="addr:street:type" v="Avenue"/>
<tag k="amenity" v="pharmacy"/>

  should be turned into:

{...
"address": {
    "housenumber": 5158,
    "street": "North Lincoln Avenue"
}
"amenity": "pharmacy",
...
}

- for "way" specifically:

  <nd ref="305896090"/>
  <nd ref="1719825889"/>

should be turned into
"node_refs": ["305896090", "1719825889"]
"""


lower = re.compile(r'^([a-z]|_)*$')
lower_colon = re.compile(r'^([a-z]|_)*:([a-z]|_)*$')
problemchars = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

CREATED = [ "version", "changeset", "timestamp", "user", "uid"]

street_type_re = re.compile(r'\b\S+\.?$', re.IGNORECASE)


expected = ["Street", "Avenue", "Boulevard", "Drive", "Court", "Place", "Square", "Lane", "Road", 
            "Trail", "Parkway", "Commons", "Way", "Loop", "East", "West", "Terrace", "Expressway", 
            "Plaza", "Hill", "Highway", "Circle"]

# UPDATE THIS VARIABLE
mapping = { "St": "Street",
            "St.": "Street",
            "Sq.": "Square",
            "Sq": "Square",
            "Ave": "Avenue",
            "Rd.": "Road",
            "Rd": "Road",
            "Blvd": "Boulevard",
            "Cir": "Circle",
            "Dr": "Drive",
            "Hwy": "Highway"
            }


def is_street_name(elem):
    return (elem.attrib['k'] == "addr:street")

def is_pc_name(elem):
    return (elem.attrib['k'] == "addr:postcode")

def is_hn_name(elem):
    return (elem.attrib['k'] == "addr:housenumber")

def update_name(name, mapping):

    # YOUR CODE HERE
    m = street_type_re.search(name)
    if m:
        street_type = m.group()
        if street_type not in expected:
            if street_type in mapping:
                name = name.replace(street_type, mapping[street_type])
            else: pass #print street_type, name

    return name



def get_lat_long(element):
    # Get coordinates
    lat = float(element.attrib['lat'])
    lon = float(element.attrib['lon'])
    return [lat, lon]

def shape_element(element):
    node = {}
    if element.tag == "node" or element.tag == "way" :
        # YOUR CODE HERE
        node['type'] = element.tag
        
        if 'lat' in element.attrib:
            node['pos'] = get_lat_long(element)
        
        node['created'] = {}
        
        # Go over 2nd level tag props 
        for tag in element.iter():
            for key, value in tag.items():
                #print key, value
                if key in CREATED:
                    node['created'][key] = value
                elif key == 'k' and re.search(problemchars, value):
                    node = None
                    break
                elif key == 'k' and value.startswith('addr:'):
                    #print "processing address..."
                    if key.count(":") > 1:
                        node = None
                        break
                    if 'address' not in node: node['address'] = {}
                    if is_street_name(tag):
                        #audit_street_type(street_types, tag.attrib['v'])
                        street_name = update_name(tag.attrib['v'], mapping)
                        #print value, tag.attrib['v'], street_name
                        node['address']['street'] = street_name
                    elif is_hn_name(tag):
                        node['address']['housenumber'] = tag.attrib['v']
                    elif is_pc_name(tag):
                        pc  = None
                        postcodes = tag.attrib['v'].split("-")
                        m = re.search('[a-zA-Z]', postcodes[0])
                        if m:
                            pcs = postcodes[0].split(" ")
                            for x in pcs:
                                n = re.search('[a-zA-Z]', x)
                                if n == None:
                                    pc = x
                                    break
                        else: pc = postcodes[0]
                        if pc == None or  len(pc) != 5:
                            node = None
                            break
                        node['address']['postcode'] = pc[0:5]
                        #print "Post code is ", node['address']['postcode']
                    else: 
                        node = None
                        break
                elif key == 'k' and value.startswith(':'): 
                    node = None
                    break
                elif key == 'k' and not value.startswith('addr'): 
                    #print value, "and", tag.attrib['v']
                    node[value] = tag.attrib['v']
                elif key == 'ref':
                    if 'node_refs' not in node: node['node_refs'] = []
                    node['node_refs'].append(value)
                elif key not in ['lat', 'lon', 'k', 'v']:
                    # Process remaining tags
                    node[key] = value
            if node == None: break
        return node
    else:
        return None


def process_map(file_in, pretty = False):
    # You do not need to change this file
    file_out = "{0}.json".format(file_in)
    data = []
    first = None
    with codecs.open(file_out, "w") as fo:
        for _, element in ET.iterparse(file_in):
            el = shape_element(element)
            if el:
                data.append(el)
                if first == None: 
                    fo.write("[")
                    first = True
                else: fo.write(",\n")
                if pretty:
                    fo.write(json.dumps(el, indent=2))
                else:
                    fo.write(json.dumps(el))
        fo.write("]")
    return data

def insert_data_bulk(db):

    # Your code here. Insert the data into a collection 'arachnid'
    num_docs = db.sanjose.find().count()
    print "num_docs before insert", num_docs

    os.system("~/mongodb/bin/mongoimport --db examples --collection sanjose --file san-jose_california.osm.json --jsonArray")
    
    num_docs = db.sanjose.find().count()
    print "num_docs after insert", num_docs

def insert_data(data, db):

    # Your code here. Insert the data into a collection 'arachnid'
    num_docs = db.sanjose.find().count()
    print "num_docs before insert", num_docs

    for a in data:
        db.sanjose.insert(a)

    num_docs = db.sanjose.find().count()
    print "num_docs after insert", num_docs

def create_data(client):
    db = client["examples"]

def remove_data(client, db):
    client.drop_database("examples")

def query_and_update_data(db):

    num_docs = db.sanjose.find().count()
    print "Number of docs", num_docs

    num_nodes = db.sanjose.find({"type":"node"}).count()
    print "Number of nodes", num_nodes

    num_ways = db.sanjose.find({"type":"way"}).count()
    print "Number of ways", num_ways

    num_hospitals = db.sanjose.find({"amenity":"hospital"}).count()
    print "Number of hospitals", num_hospitals

    num_schools = db.sanjose.find({"amenity":"school"}).count()
    print "Number of schools", num_schools
    
    num_univ = db.sanjose.find({"amenity":"university"}).count()
    print "Number of univ", num_univ
    
    #num_users = db.sanjose.distinct({"created.user"}).length
    #print "Number of users", num_users

    top_user = [doc for doc in db.sanjose.aggregate([{"$group":{"_id":"$created.user", "count":{"$sum":1}}}, 
                                  {"$sort":{"count":-1}}, 
                                  {"$limit":1}])]
    print
    print "top_user..."
    pprint.pprint(top_user)

    user_1time = [doc for doc in db.sanjose.aggregate([{"$group":{"_id":"$created.user", "count":{"$sum":1}}}, 
                                    {"$group":{"_id":"$count", "num_users":{"$sum":1}}}, 
                                    {"$sort":{"_id":1}}, {"$limit":1}])]
    print
    print "1 time user..."
    pprint.pprint(user_1time)

    pc_sorted = [doc for doc in db.sanjose.aggregate([{"$match":{"address.postcode":{"$exists":1}}}, 
                                      {"$group":{"_id":"$address.postcode", "count":{"$sum":1}}}, 
                                      {"$sort":{"count":-1}}])]
    print
    print "Most used postcodes..."
    pprint.pprint(pc_sorted)

    """
    cities_sorted = [doc for doc in db.sanjose.aggregate([{"$match":{"address.city":{"$exists":1}}}, 
                                        {"$group":{"_id":"$address.city", 
                                        "count":{"$sum":1}}}, 
                                        {"$sort":{"count":-1}}])]
    
    print
    print "Most appearing cities..."
    pprint.pprint(cities_sorted)
    """

    top10_amenities = [doc for doc in db.sanjose.aggregate([{"$match":{"amenity":{"$exists":1}}}, 
                                         {"$group":{"_id":"$amenity", "count":{"$sum":1}}}, 
                                         {"$sort":{"count":-1}}, 
                                         {"$limit":10}])]
    print
    print "top 10 amenities..."
    pprint.pprint(top10_amenities)

    
    all_univ = [doc for doc in db.sanjose.aggregate([{"$match":{"amenity":{"$exists":1}, "name":{"$exists":1}, "amenity":"university"}},
                                          {"$group":{"_id":"$name", "count":{"$sum":1}}},
                                          {"$sort":{"count":-1}}])]
    print
    print "All univ..."
    pprint.pprint(all_univ)

    biggest_religion = [doc for doc in db.sanjose.aggregate([{"$match":{"amenity":{"$exists":1}, "amenity":"place_of_worship"}},
                                          {"$group":{"_id":"$religion", "count":{"$sum":1}}},
                                          {"$sort":{"count":-1}}, {"$limit":1}])]
    print
    print "biggest religion..."
    pprint.pprint(biggest_religion)

    popular_cuisines = [doc for doc in db.sanjose.aggregate([{"$match":{"amenity":{"$exists":1},
                                                                        "cuisine":{"$exists":1}, 
                                                                        "amenity":"restaurant"}}, 
                                        {"$group":{"_id":"$cuisine", "count":{"$sum":1}}},        
                                        {"$sort":{"count":-1}}])]
    print
    print "popular cuisines..."
    pprint.pprint(popular_cuisines)

    indian_cuisines = [doc for doc in db.sanjose.aggregate([{"$match":{"amenity":{"$exists":1},
                                                                        "cuisine":"indian", 
                                                                        "amenity":"restaurant"}}, 
                                        {"$group":{"_id":"$name", "count":{"$sum":1}}},        
                                        {"$sort":{"count":-1}}])]
    print
    print "indian cuisines... total: ", db.sanjose.find({"cuisine":"indian", "amenity":"restaurant"}).count()
    pprint.pprint(indian_cuisines)

    ll = db.sanjose.find_one({"name": "L&L Hawaiian BBQ"})
    ll['cuisine'] = "American"
    db.sanjose.save(ll)
    
    indian_cuisines = [doc for doc in db.sanjose.aggregate([{"$match":{"amenity":{"$exists":1},
                                                                        "cuisine":"indian", 
                                                                        "amenity":"restaurant"}}, 
                                        {"$group":{"_id":"$name", "count":{"$sum":1}}},        
                                        {"$sort":{"count":-1}}])]
    print
    print "indian cuisines... total: ", db.sanjose.find({"cuisine":"indian", "amenity":"restaurant"}).count()
    pprint.pprint(indian_cuisines)


def test():
    # NOTE: if you are running this code on your computer, with a larger dataset, 
    # call the process_map procedure with pretty=False. The pretty=True option adds 
    # additional spaces to the output, making it significantly larger.
    
    
    data = process_map('san-jose_california.osm', False)
    #pprint.pprint(data)


    from pymongo import MongoClient
    client = MongoClient("mongodb://localhost:27017")
    create_data(client)
    db = client.examples

    """
    # this is non-batched data insert into db
    with open('san-jose_california.osm.json') as f:
        data = json.loads(f.read())
        insert_data(data, db) 
        #print db.sanjose.find_one()
        query_and_update_data(db)
        remove_data(client, db)
    """

    insert_data_bulk(db) 
    query_and_update_data(db)
    remove_data(client, db)



if __name__ == "__main__":
    test()
