import argparse
import glob
import json
import os
import requests
import cchardet
import lxml
from bs4 import BeautifulSoup
from tqdm import tqdm
from datetime import datetime


# classname of price element
PRICE_CLASSNAME = 'OfferPriceCaption__price' # span
# name of atributes as displayed on HTML page
BODY_TYPE_ATRIBUTE = 'bodytype'
COLOR_ATRIBUTE = 'color'
ENGINE_ATRIBUTE = 'engine'
MILEAGE_ATRIBUTE = 'kmAge'
YEAR_ATRIBUTE = 'year'
TRANSMISSION_ATRIBUTE = 'transmission'
OWNERS_COUNT_ATRIBUTE = 'ownersCount'
PTS_ATRIBUTE = 'pts'
DRIVE_ATRIBUTE = 'drive'
WHEEL_ATRIBUTE = 'wheel'
# combine all atributes into one list
ALL_ATRIBUTES = [BODY_TYPE_ATRIBUTE, COLOR_ATRIBUTE, ENGINE_ATRIBUTE, MILEAGE_ATRIBUTE, YEAR_ATRIBUTE, 
                TRANSMISSION_ATRIBUTE, OWNERS_COUNT_ATRIBUTE, PTS_ATRIBUTE, DRIVE_ATRIBUTE, WHEEL_ATRIBUTE]
# mapping from atribute name to feature name
ATRIBUTE_TO_FEATURE_MAPPING = {
    'bodytype': 'bodyType',
    'kmAge': 'mileage',
    'transmission': 'vehicleTransmission',
    'ownersCount': 'Владельцы',
    'pts': 'ПТС',
    'drive': 'Привод',
    'wheel': 'Руль'
}


"""
Simple builder of atribute HTML class
"""
def get_atribute_classname(atribute):
    return f'CardInfoRow_{atribute}'


"""
Convert string into integer
"""
def convert_string_to_int(s):
    value = ''.join([c for c in s if c.isdigit()])
    return int(value)


"""
Splits engine information string into three atributes
"""
def get_engine_characteristics(engine_atributes):
    # split string by /
    splitted = engine_atributes.split('/')

    # check if we have 3 entries
    if len(splitted) < 3:
        print(engine_atributes)
        return 0.0, 0.0, splitted[0].strip().lower()

    # extract each engine characteristic
    engine_volume = splitted[0].split()[0]
    engine_power = ''.join([c for c in splitted[1].split()[0] if c.isdigit()])
    fuel_type = splitted[2].strip().lower()
    
    return float(engine_volume), float(int(engine_power)), fuel_type


"""
Retrieve page and parse using lxml parser
"""
def get_car_page(car_url, timeout=3):
    try:
        response = requests.get(car_url, timeout=timeout)
    except requests.exceptions.RequestException:
        return None
    
    # check response status code
    if response.status_code != 200:
        return None
    
    # set response encoding to UTF-8; removes gibberish characters in response text
    response.encoding = 'utf-8'
    # parse response text with bs4
    soup = BeautifulSoup(response.text, 'lxml')
    
    return soup


"""
Combine previous functions and extract atribute values
"""
def get_car_info(car_url, brand, model, vendor):
    # retrieve and parse car page
    car_page = get_car_page(car_url)
    # build car info dictionary
    info_dict = dict()
    info_dict['car_url'] = car_url
    info_dict['brand'] = brand
    info_dict['model_name'] = model
    info_dict['vendor'] = vendor

    # return if car page is parsed with error
    if car_page is None:
        return info_dict
    
    # extract price
    price_element = car_page.find('span', class_=PRICE_CLASSNAME)
    # add price to dictionary
    if price_element is None:
        info_dict['price'] = None
    else:
        info_dict['price'] = convert_string_to_int(price_element.get_text())
    
    # extract atributes
    for atribute in ALL_ATRIBUTES:
        # find atribute element
        atribute_element = car_page.find('li', class_=get_atribute_classname(atribute))
        
        if atribute_element:
            # get its <span> children (one has atribute name and other has value)
            atribute_element_span_children = atribute_element.find_all('span')
            # extract atribute value
            atribute_value = atribute_element_span_children[-1].get_text().replace('\xa0', ' ')
            
            # split engine characteristics
            if atribute == ENGINE_ATRIBUTE:
                engine_volume, engine_power, fuel_type = get_engine_characteristics(atribute_value)
                info_dict['engineDisplacement'] = engine_volume
                info_dict['enginePower'] = engine_power
                info_dict['fuelType'] = fuel_type
                continue
                
            # modify mileage value
            if atribute == MILEAGE_ATRIBUTE:
                atribute_value = convert_string_to_int(atribute_value)
            
            # update car info dictionary
            if atribute in ATRIBUTE_TO_FEATURE_MAPPING:
                info_dict[ATRIBUTE_TO_FEATURE_MAPPING[atribute]] = atribute_value
            else:
                info_dict[atribute] = atribute_value
        
    return info_dict


if __name__ == "__main__":
    # argument parser setup
    parser = argparse.ArgumentParser()
    parser.add_argument('--brand', help="name of car brand")
    args = parser.parse_args()

    # set paths
    base_dir = 'data'
    links_dir = os.path.join(base_dir, 'links')
    save_dir = os.path.join(base_dir, 'cars', args.brand)

    # create directory for output
    os.makedirs(save_dir, exist_ok=True)

    # open brands/vendors dictionary
    with open(os.path.join(base_dir, 'brands_vendors_dict.json'), 'r') as file:
        brands_vendors_dict = json.load(file)
    # open dictionaries with number of links by brand and brand/model
    with open(os.path.join(base_dir, 'links_by_brand.json'), 'r') as file:
        links_by_brand = json.load(file)
    with open(os.path.join(base_dir, 'links_by_brand_model.json'), 'r') as file:
        links_by_brand_model = json.load(file)
    
    print(f"Total number of links for {args.brand}: {links_by_brand[args.brand]}")
    
    # iterate through .json file for each car model of specified brand
    for model_path in tqdm(glob.glob(os.path.join(links_dir, args.brand, '*.json'))):
        # extract model name
        model = os.path.basename(model_path)[:-5]
        # path for saving current model cars information
        save_path = os.path.join(save_dir, f'{model}.json')

        # skip if there is JSON file already
        if os.path.exists(save_path):
            print(f"\n\tSkipping brand: {args.brand}, model: {model}")
            continue

        print(f"\tBrand: {args.brand}, model: {model}, number of links: {links_by_brand_model[args.brand][model]}")

        # open list of links for current car model
        with open(model_path, 'r') as file:
            model_links_list = json.load(file)

        # create a list for storing information dictionaries
        model_cars_info_list = list()

        # iterate through each car listing link
        for i, car_url in enumerate(model_links_list):
            # print every 50 iterations
            if i % 50 == 0:
                print(f"\t\tCar {i+1}/{links_by_brand_model[args.brand][model]}")
            # get car details and return info dictionary
            car_info = get_car_info(car_url, args.brand, model, brands_vendors_dict[args.brand])
            # add to model cars list
            model_cars_info_list.append(car_info)

        # save list to JSON file
        with open(save_path, 'w') as file:
            json.dump(model_cars_info_list, file)