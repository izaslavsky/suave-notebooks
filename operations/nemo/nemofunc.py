import re
import requests
import pandas as pd
import xml.etree.ElementTree as ET
import json
import urllib
from IPython.display import Markdown, display

def printmd(string):
    display(Markdown(string))

# import credentials file
import yaml
from pathlib import Path
try:
    with open(Path.home() / 'creds.yml', 'r') as ymlfile:
        cfg = yaml.safe_load(ymlfile)
except IOError:
    printmd("<b><span style='color:red;font-size:200%'>API KEY NOT AVAILABLE. CANNOT CONTINUE.</span></b>")

    
# general way to extract values for a given key. Returns an array. Used to parse Nemo response and extract wikipedia id
# from https://hackersandslackers.com/extract-data-from-complex-json-python/

def extract_values(obj, key):
    """Pull all values of specified key from nested JSON."""
    arr = []

    def extract(obj, arr, key):
        """Recursively search for values of key in JSON tree."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    extract(v, arr, key)
                elif k == key:
                    arr.append(v)
        elif isinstance(obj, list):
            for item in obj:
                extract(item, arr, key)
        return arr

    results = extract(obj, arr, key)
    return results

# getting wikipedia ID
# see he API at https://www.mediawiki.org/wiki/API:Query#Example_5:_Batchcomplete
# also, https://stackoverflow.com/questions/37024807/how-to-get-wikidata-id-for-an-wikipedia-article-by-api

def get_WPID (name):
    url = 'https://en.wikipedia.org/w/api.php?action=query&prop=pageprops&ppprop=wikibase_item&redirects=1&format=json&titles=' +urllib.parse.quote(name)
    r=requests.get(url).json()
    try:
        ret = extract_values(r,'wikibase_item')[0]
    except:
        ret =''
    return ret
    
    
def nemo_annotate(payload):

#remove special characters and new lines, just in case
    payload = re.sub('[^a-zA-Z0-9\n\.]', ' ', payload)
    payload = payload.replace('\n',' ').strip()
    payload = payload.replace('|',' ')
    payload = str(payload.encode('utf-8'))
    
    # make a service request

    url = "https://nemoservice.azurewebsites.net/nemo?appid=" + cfg['api_creds']['nmo1']
    #url = "https://nemoservice.azurewebsites.net/nemo?appid=B1970F7D921F52F50129C27936D1F2AF794ADB11"
    newHeaders = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    response = requests.post(url,
                             data='"{' + payload + '}"',
                             headers=newHeaders)    

    # display the results as string (remove json braces)
    a = response.content.decode('utf-8')
    resp_full = a[a.find('{')+1 : a.find('}')]
    
    # create a dataframe with entities, remove duplicates, then add wikipedia/wikidata concept IDs
    df = pd.DataFrame(columns=["Type","Ref","EntityType","Name","Form","WP","Value","Alt","WP_ID"])
    
 
    # get starting and ending positions of xml fragments in the Nemo output
    pattern_start = "<(e|d|c)\s"
    iter = re.finditer(pattern_start,resp_full)
    indices1 = [m.start(0) for m in iter]
    pattern_end = "</(e|d|c)>"
    iter = re.finditer(pattern_end,resp_full)
    indices2 = [m.start(0) for m in iter]

    # iterate over xml fragments returned by Nemo, extracting attributes from each and adding to dataframe
    for i, entity in enumerate(indices1):
        a = resp_full[indices1[i] : indices2[i]+4]
        a = a.replace("&","&amp;").replace("'", "&apos;")

        
        try:
            root = ET.fromstring(a)
            tag = root.tag
            attributes = root.attrib

            df = df.append({"Type":root.tag, 
                    "Ref":attributes.get('ref'),
                    "EntityType":attributes.get('type'),
                    "Name":attributes.get('name'),
                    "Form":attributes.get('form'),
                    "WP":attributes.get('wp'),
                    "Value":attributes.get('value'),
                    "Alt":attributes.get('alt')},
                   ignore_index=True)        
        except:
            continue
    
    # remove duplicate records from the df
    df = df.drop_duplicates(keep='first')   

    # for each found entity, add wikidata unique identifiers to the dataframe
    for index, row in df.iterrows():
        if (row['WP']=='y'):
            row['WP_ID'] = get_WPID(row['Ref'])

    return df, resp_full

def create_nemo_dict(nemotable):

# define a dictionary where keys will be column names and values will be values for this ME<O result 
    this_dict = {}   

    nemotable['WP'].fillna(value='n', inplace = True)

# create a new column for groupby
    nemotable['combo'] = nemotable['Type'] + "_" + nemotable['EntityType'] + "-" + nemotable['WP']
    all_combos = nemotable['combo'].unique().tolist()
#     all_combos
# create a new dataframe with the columns we need only
    selected_columns = nemotable[["Ref","WP_ID",'Value','combo']]
    df1 = selected_columns.copy()

# generate three types of tables. Note that they use different columns from the NEMO response
    entities_concepts = df1.groupby('combo')['Ref'].apply(list).reset_index(name='thislist')
    data_fields = df1.groupby('combo')['Value'].apply(list).reset_index(name='thislist')
    WPIDs = df1.groupby('combo')['WP_ID'].apply(list).reset_index(name='thislist')
    
# Process the first table (entities and concepts)
# drop rows that contain "d_" (data fields)
    entities_concepts = entities_concepts[~entities_concepts['combo'].str.contains('d_')]

# add them to the dictionary
    for index, row in entities_concepts.iterrows():
        this_dict.update( { row['combo'] : '|'.join(row['thislist'])})

# Process the second table (entries that include data values)
# only keep rows that contain d_, that is, contain data entries
    data_fields = data_fields[data_fields['combo'].str.contains('d_')]

# add them to the dictionary
    for index, row in data_fields.iterrows():
        this_dict.update( { row['combo'] : '|'.join(row['thislist'])})

# Process the third table (entries that have associated WP links)
# only keep rows that contain -y, that is, contain WP links
    WPIDs = WPIDs[WPIDs['combo'].str.contains('-y')]

# add them to the dictionary, changing keys to reflect that these are WP links, and changing values to URLs
#     for index, row in WPIDs.iterrows():
#         url_list = ["http://wikidata.org/wiki/"+e for e in row['thislist']]
#         this_dict.update( { row['combo']+"_WP" : '|'.join(url_list)})

# version with URLs wrapped in html:
    for index, row in WPIDs.iterrows():
        key_name = (row['combo'])
        concept_names = this_dict[key_name].split("|")
        url_list =[]
        for x in range(len(row['thislist'])):
            concept = concept_names[x]
            wikidata = row['thislist'][x]
            url_list.append("<a href='http://wikidata.org/wiki/"+ wikidata + "' target='_blank'>"+ concept+"</a>")
        this_dict.update( { row['combo']+"_WP" : '<br/>'.join(url_list)})


    return this_dict

def column_order():
    cols = [
        "c_U-n",
        "c_U-y", "c_U-y_WP",
        "c_C-y", "c_C-y_WP",
        "c_W-y", "c_W-y_WP",
        "e_N-y", "e_N-y_WP",
        "e_C-y", "e_C-y_WP",
        "e_G-y", "e_G-y_WP",
        "e_O-y", "e_O-y_WP",
        "e_M-y", "e_M-y_WP",
        "e_U-y", "e_U-y_WP",
        "e_F-y", "e_F-y_WP",
        "e_H-y", "e_H-y_WP",
        "e_W-y", "e_W-y_WP",
        "e_L-y", "e_L-y_WP",
        "e_P-y", "e_P-y_WP",
        "e_J-y", "e_J-y_WP",
        "e_V-y", "e_V-y_WP",
        "e_A-y", "e_A-y_WP",
        "e_I-y", "e_I-y_WP",
        "e_B-y", "e_B-y_WP",
        "e_Y-y", "e_Y-y_WP",
        "e_S-y", "e_S-y_WP", 
        "e_E-y", "e_E-y_WP",
        "e_K-y", "e_K-y_WP",
        "e_R-y", "e_R-y_WP",
        "e_Q-y", "e_Q-y_WP",
        "e_U-n", 
        "e_D-d", 
        "d_url-n", 
        "d_quantity-n", 
        "d_age-n", 
        "d_phone-n", 
        "d_street-n", 
        "d_date-n"
    ]
    return cols
    
def columns_dict():
    # this is a complete list of columns to rename
    col_dict = {
        "c_U-n": "Concept: Common Phrase#multi#sortquan",
        "c_U-y": "Concept: Formal Term#multi#sortquan",
        "c_U-y_WP": "Concept: Formal Term URL#hidden",
        "c_C-y": "Concept: Abstract#multi#sortquan",
        "c_C-y_WP": "Concept: Abstract URL#hidden",
        "c_W-y": "Concept W#multi#sortquan",
        "c_W-y_WP": "Concept W URL#hidden",

        "e_N-y": "Entity: Covid Term#multi#sortquan",
        "e_N-y_WP": "Entity: Covid Term URL#hidden",
        "e_C-y": "Entity: Abstract#multi#sortquan",
        "e_C-y_WP" : "Entity: Abstract URL#hidden",
        "e_G-y": "Entity: Geopolitical#multi#sortquan",
        "e_G-y_WP": "Entity: Geopolitical URL#hidden",
        "e_O-y": "Entity: Organization#multi#sortquan",
        "e_O-y_WP": "Entity: Organization URL#hidden",
        "e_M-y": "Entity: Media#multi#sortquan",
        "e_M-y_WP": "Entity: Media URL#hidden",
        "e_U-y": "Entity: Formal#multi#sortquan",
        "e_U-y_WP": "Entity: Formal URL#hidden",
        "e_F-y": "Entity: Facility#multi#sortquan",
        "e_F-y_WP": "Entity: Facility URL#hidden",
        "e_H-y": "Entity: Holidays#multi#sortquan",
        "e_H-y_WP": "Entity: Holidays URL#hidden",
        "e_W-y": "Entity: Arts#multi#sortquan",
        "e_W-y_WP": "Entity: Arts URL#hidden",
        "e_L-y": "Entity: Location#multi#sortquan",
        "e_L-y_WP": "Entity: Location URL#hidden",
        "e_P-y": "Entity: Personal#multi#sortquan",
        "e_P-y_WP": "Entity: Personal URL#hidden",
        "e_J-y": "Entity: Computer Term#multi#sortquan",
        "e_J-y_WP": "Entity: Computer Term URL#hidden",
        "e_V-y": "Entity: Vehicle#multi#sortquan",
        "e_V-y_WP": "Entity: Vehicle URL#hidden",
        "e_A-y": "Entity: Medical#multi#sortquan",
        "e_A-y_WP": "Entity: Medical URL#hidden",
        "e_I-y": "Entity: Informatic#multi#sortquan",
        "e_I-y_WP": "Entity: Informatic URL#hidden",
        "e_B-y": "Entity: Linguistic#multi#sortquan",
        "e_B-y_WP": "Entity: Linguistic URL#hidden",
        "e_Y-y": "Entity: Peoples#multi#sortquan",
        "e_Y-y_WP": "Entity: Peoples URL#hidden",
        "e_S-y": "Entity: Transportation#multi#sortquan",
        "e_S-y_WP": "Entity: Transportation URL#hidden",
        "e_E-y": "Entity: Event#multi#sortquan",
        "e_E-y_WP": "Entity: Event URL#hidden",
        "e_K-y": "Entity: Bureaucratic#multi#sortquan",
        "e_K-y_WP": "Entity: Bureaucratic URL#hidden",
        "e_R-y": "Entity R#multi#sortquan",
        "e_R-y_WP": "Entity R URL#hidden",
        "e_Q-y": "Entity Q#multi#sortquan",
        "e_Q-y_WP": "Entity Q URL#hidden",

        "e_U-n": "Entity: Formal no-URL#multi#sortquan",

        "e_D-d": "Entity for Disambiguation#multi#sortquan",

        
        "d_url-n": "Data URL#hidden",
        "d_quantity-n": "Quantity#multi#sortquan",
        "d_age-n": "Age#multi#sortquan",
        "d_phone-n": "Phone#multi#sortquan",
        "d_street-n": "Street#multi#sortquan",
        "d_date-n": "Date#multi#sortquan"
        
    }
    return col_dict
    
