import argparse
import json
import logging
import os
import requests
import cchardet
import lxml
from bs4 import BeautifulSoup
from tqdm import tqdm
from datetime import datetime


# base request address
BASE_URL = 'https://auto.ru/cars'
# pagination class
PAGINATION_CLASS = 'ListingPagination-module__pages'  # span
# listing item link class
ITEM_LINK_CLASS = 'ListingItemTitle-module__link'  # a


"""
Get number of total pages from pagination element
"""
def get_pages_number(soup):
    # search for pagination element
    pagination = soup.find('span', class_=PAGINATION_CLASS)

    # return 1 if pagination element is not found
    if pagination is None:
        return 1

    # find <a> children, i.e. links
    links = pagination.find_all('a')

    # return text of last link (converted to integer)
    return int(links[-1].get_text())


"""
Get all links from listing items on page
"""
def get_item_links(soup):
    # search for item listing links
    item_links = soup.find_all('a', class_=ITEM_LINK_CLASS)
    # extract links only, i.e. href only
    item_links = [link['href'] for link in item_links]

    return item_links


"""
Retrieve page by URL and parse using lxml
"""
def parse_one_page(brand, model, page):
    # build page query; empty if page is 1 and ?page=n otherwise
    page_query = '' if page == 1 else f'/?page={page}'
    # build request URL
    request_url = f'{BASE_URL}/{brand}/{model}/all{page_query}'
    # send GET request
    try:
        response = requests.get(request_url, timeout=3)
    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.RequestException:
        return None

    # set response encoding to UTF-8; removes gibberish characters in response text
    response.encoding = 'utf-8'
    # parse response text with bs4
    soup = BeautifulSoup(response.text, 'lxml')

    return soup


"""
Parse all links for defined list of (brand, model) tuples
"""
def parse_all_item_links(brands_models_list):
    # iterate through (brand, model) tuples
    for (brand, model) in tqdm(brands_models_list):
        # transform to lowercase
        brand = brand
        model = model
        print(f"brand: {brand}, model: {model}")
        logging.info("brand: %s, model: %s", brand, model)

        # create directory for brand
        os.makedirs(os.path.join('data', 'links', brand), exist_ok=True)
        # build path for JSON file
        json_path = os.path.join('data', 'links', brand, f'{model}.json')
        # skip model if JSON file exists
        if os.path.exists(json_path):
            print("skipping...")
            logging.info("skipping...")
            continue

        # build list of links for current model
        model_links_list = list()
        # parse first page
        first_page_soup = parse_one_page(brand, model, 1)
        # skip model if first page couldn't be processed
        if first_page_soup is None:
            print("\tskipping page 1 due to connection timeout/error")
            logging.info("skipping page 1 due to connection timeout/error")
            continue

        # get number of pages
        pages_number = get_pages_number(first_page_soup)
        # add links from first page
        model_links_list.extend(get_item_links(first_page_soup))
        print(f"\tprocessed page 1/{pages_number} ({len(model_links_list)} items)")
        logging.info("processed page 1/%d (%d)", pages_number, len(model_links_list))

        # continue if more than 1 page
        if pages_number > 1:
            for i in range(2, pages_number + 1):
                # parse current page
                page_soup = parse_one_page(brand, model, i)
                # skip page if error occurred
                if page_soup is None:
                    print(f"\tskipping page {i} due to connection timeout/error")
                    logging.info("skipping page %d due to connection timeout/error", i)
                    continue
                # add links from page
                model_links_list.extend(get_item_links(page_soup))
                print(f"\tprocessed page {i}/{pages_number} ({len(model_links_list)} items)")
                logging.info("processed page %d/%d (%d items)", i, pages_number, len(model_links_list))

        # save list to JSON
        with open(json_path, 'w') as file:
            json.dump(model_links_list, file)


if __name__ == "__main__":
    # argument parser setup
    parser = argparse.ArgumentParser()
    parser.add_argument('--dict_path', help="path to file containing dictionary with car brands/models")
    args = parser.parse_args()

    # logging setup
    # configure all messages higher than DEBUG to go into file
    time_str = datetime.now().strftime('%Y_%m_%d-%H_%M_%S')
    logging.basicConfig(filename=f'logs/script_collect_links_{time_str}.log', level=logging.DEBUG)


    # open dictionary with car brands and corresponding models
    with open(args.dict_path, 'r') as file:
        brands_models_dict = json.load(file)

    # build list with (brand, model) tuples
    # flattens dictionary for proper tqdm progress report
    brands_models_list = list()

    for brand in tqdm(brands_models_dict.keys()):
        logging.debug("processing brand: %s", brand)
        # get all unique model names
        brand_models = brands_models_dict[brand]
        # add entries to list
        for model in brand_models:
            brands_models_list.append((brand, model))

    # start parsing
    parse_all_item_links(brands_models_list)