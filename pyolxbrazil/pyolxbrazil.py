from bs4 import BeautifulSoup
import requests
from fake_useragent import UserAgent
import json
import re
import datetime
import math

# Fake user-agent
ua = UserAgent()
header = {'User-Agent': str(ua.random)}

# State abbreviations to full names
state_map = {
    'ac': 'Acre', 'al': 'Alagoas', 'ap': 'Amapá', 'am': 'Amazonas', 'ba': 'Bahia',
    'ce': 'Ceará', 'df': 'Distrito Federal', 'es': 'Espírito Santo', 'go': 'Goiás',
    'ma': 'Maranhão', 'mt': 'Mato Grosso', 'ms': 'Mato Grosso do Sul', 'mg': 'Minas Gerais',
    'pa': 'Pará', 'pb': 'Paraíba', 'pr': 'Paraná', 'pe': 'Pernambuco', 'pi': 'Piauí',
    'rj': 'Rio de Janeiro', 'rn': 'Rio Grande do Norte', 'rs': 'Rio Grande do Sul',
    'ro': 'Rondônia', 'rr': 'Roraima', 'sc': 'Santa Catarina', 'sp': 'São Paulo',
    'se': 'Sergipe', 'to': 'Tocantins'
}

# Months - abbreviations
months = {'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04', 'mai': '05',
          'jun': '06', 'jul': '07', 'ago': '08', 'set': '09', 'out': '10',
          'nov': '11', 'dez': '12'}


class OLXBrazil:
    """A class used to scrape ad data from OLX website (http://www.olx.com.br).

    Attributes
    ----------
    search : str
        searched item on OLX

    state : str
        initials of the brazilian state where the item is located.
        For example, state='ce' (for Ceará)
                  or state='rj' (for Rio de Janeiro)

    Methods
    -------
    extract(filter_by='relevance', all_pages=False, limit=None):
        Return a list containing all items available.
            filter_by (str):
                relevance (Default): most relevant items
                price: cheapest price for the items
                new: recently added items on the website

            all_pages (bool):
                False (Default): return the first page searched
                                 or until the "limit" (parameter) page
                True: return all the pages searched

            limit (int or None):
                Page limit searched.
                    If "all_pages" is True, then "limit" should be None (Default).
                    If "all_pages" is False, then "limit" can be None or int.

    unique_extract(url, complete=False):
        Return a dictionary containing the ad information.
            url (str):
                item URL
            complete (bool):
                False (Default): relevant ad information
                True: complete ad information
    """

    def __init__(self, search, state):
        self._search = search
        self._state = state

    def __str__(self):
        return OLXBrazil.__doc__

    # Get number of pages
    def __number_of_pages(self, soup):
        """Extracts the total number of pages from the dataLayer script."""
        try:
            # OLX now provides total ad count in a script tag
            script_tag = soup.find('script', id='datalayer')
            if not script_tag:
                return None

            # Extract the JSON-like string from the script
            match = re.search(r'dataLayer\.push\((.*)\)', script_tag.string, re.DOTALL)
            if not match:
                return None

            # Clean up the string to be valid JSON
            json_str = match.group(1).strip()
            if json_str.endswith(','):
                json_str = json_str[:-1]

            data = json.loads(json_str)
            total_ads = data.get('page', {}).get('totalOfAds')

            if total_ads:
                # Each page usually contains 50 ads
                return math.ceil(total_ads / 50)
        except (json.JSONDecodeError, AttributeError, KeyError, TypeError):
            # Fallback in case of parsing errors
            return None
        return None

    # Search by relevance, price or new products
    def __olx_requests(self, filter_by='relevance', page=1):
        # relevance = most relevant
        # price = cheapest
        # new = newest

        if filter_by == 'relevance':
            link = f'https://{self._state}.olx.com.br/?o={page}&q={self._search}'
        elif filter_by == 'price':
            link = f'https://{self._state}.olx.com.br/?o={page}&q={self._search}&sp=1'
        elif filter_by == 'new':
            link = f'https://{self._state}.olx.com.br/?o={page}&q={self._search}&sf=1'
        else:
            # Default to relevance if filter_by is invalid
            link = f'https://{self._state}.olx.com.br/?o={page}&q={self._search}'

        response = requests.get(link, headers=header)
        soup = BeautifulSoup(response.text, "html.parser")
        return soup

    # Get unique product information
    @staticmethod
    def unique_extract(url, complete=False):
        """Return a dictionary containing the ad information.
            url (str):
                item URL
            complete (bool):
                False (Default): relevant ad information
                True: complete ad information

            NOTE: This method relies on a JSON data island from a single ad page.
                  Its structure might have changed, and information like phone numbers
                  is often protected, so this method may be broken.
        """
        if 'olx.com' in url:
            response = requests.get(url, headers=header)
            soup = BeautifulSoup(response.text, "html.parser")

            # Information dictionary
            product_dict_unique = {}

            # JSON data island
            initial_data_script = soup.find('script', {'id': 'initial-data'})
            if not initial_data_script:
                return {"error": "Could not find initial-data script. Page structure may have changed."}

            general_info = json.loads(initial_data_script['data-json'])['ad']

            # Complete information
            if complete is True:
                return general_info

            # Partial information
            product_dict_unique['Name'] = general_info.get('subject')
            product_dict_unique['ID'] = general_info.get('listId')
            if general_info.get('images'):
                product_dict_unique['Image'] = general_info['images'][0]['original']
            product_dict_unique['Price'] = re.findall(r'R\$ ([\d.,]+)', general_info.get('priceValue', ''))[0].replace('.', '').replace(',', '.')
            product_dict_unique['Description'] = general_info.get('description')
            product_dict_unique['Datetime (UTC)'] = general_info.get('listTime')
            product_dict_unique['Author'] = general_info.get('user', {}).get('name')
            product_dict_unique['Phone'] = general_info.get('phone', {}).get('phone')
            product_dict_unique['Type'] = general_info.get('parentCategoryName')
            product_dict_unique['Category'] = general_info.get('categoryName')
            product_dict_unique['Location'] = general_info.get('location')

            return product_dict_unique
        return {"error": "Invalid URL provided."}

    # Scrapping
    def extract(self, filter_by='relevance', all_pages=False, limit=None):
        """Return a list containing all items available.
                filter_by (str):
                    relevance (Default): most relevant items
                    price: ascending price for the items
                    new: recently added items on the website

                all_pages (bool):
                    False (Default): return the first page searched
                                    or until the "limit" (parameter) page
                    True: return all the pages searched

                limit (int or None):
                    Page limit searched.
                        If "all_pages" is True, then "limit" should be None (Default).
                        If "all_pages" is False, then "limit" can be None or int.
        """
        page = 1
        total_of_pages = 1
        products_list = []

        while page <= total_of_pages:
            soup = self.__olx_requests(filter_by, page)
            
            # Set total pages on the first iteration
            if page == 1:
                max_pages = self.__number_of_pages(soup)
                if all_pages and max_pages:
                    total_of_pages = max_pages
                elif isinstance(limit, int):
                    total_of_pages = min(limit, max_pages) if max_pages else limit
            
            # Find the main container for the ad list
            main_content = soup.find('main', id='main-content')
            ad_list_container = main_content.find('div', class_='AdListing_adListContainer__ALQla') if main_content else None

            if not ad_list_container:
                if "Nenhum anúncio foi encontrado" in soup.text:
                    print(f"Info: No ads found for this search on page {page}.")
                else:
                    print(f"Warning: Ad list container not found on page {page}. Website layout may have changed.")
                break

            # Find all ad cards in the container
            for each_product in ad_list_container.findAll('section', {'class': 'olx-adcard'}):
                product_dict = {}

                # Link and ID
                link_tag = each_product.find('a', class_='olx-adcard__link')
                if not link_tag or not link_tag.has_attr('href'):
                    continue
                product_link = link_tag['href']
                product_dict['Link'] = product_link
                try:
                    product_dict['ID'] = product_link.split('-')[-1]
                except IndexError:
                    product_dict['ID'] = '-'

                # Name
                title_tag = each_product.find('h2', class_='olx-adcard__title')
                product_dict['Name'] = title_tag.text.strip() if title_tag else 'N/A'

                # Image
                img_tag = each_product.find('img')
                product_dict['Image'] = img_tag['src'] if img_tag and img_tag.has_attr('src') else '-'

                # Price
                price_tag = each_product.find('h3', class_='olx-adcard__price')
                if price_tag and price_tag.text:
                    price_str = price_tag.text
                    # Cleans price string like "R$ 1.500,00" to "1500.00"
                    product_dict['Price'] = re.sub(r'[^\d,]', '', price_str).replace(',', '.')
                else:
                    product_dict['Price'] = '-'

                # Date and Location
                loc_date_tag = each_product.find('p', class_='olx-adcard__location-date-text')
                if loc_date_tag and loc_date_tag.text:
                    parts = [p.strip() for p in loc_date_tag.text.split('|')]
                    if len(parts) == 2:
                        location_part, date_part = parts
                        # Location
                        loc_details = [ld.strip() for ld in location_part.split(',')]
                        product_dict['City'] = loc_details[0] if loc_details else ''
                        product_dict['Neighborhood'] = loc_details[1] if len(loc_details) > 1 else ''
                        
                        # Date
                        date_part_lower = date_part.lower()
                        if 'hoje' in date_part_lower:
                            day_str = datetime.date.today().strftime("%d/%m/%Y")
                            time_str = date_part.split(',')[-1].strip()
                            product_dict['Datetime'] = f"{day_str} {time_str}"
                        elif 'ontem' in date_part_lower:
                            day_str = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%d/%m/%Y")
                            time_str = date_part.split(',')[-1].strip()
                            product_dict['Datetime'] = f"{day_str} {time_str}"
                        else:
                            try:
                                # Format: "25 jun, 15:20"
                                d_comp = date_part.replace(',', '').lower().split()
                                day, month_abbr, time_str = d_comp[0], d_comp[1], d_comp[2]
                                month_num = months.get(month_abbr, '??')
                                year = datetime.date.today().strftime("%Y")
                                product_dict['Datetime'] = f"{day}/{month_num}/{year} {time_str}"
                            except (IndexError, KeyError):
                                product_dict['Datetime'] = date_part # Fallback
                    else: # Fallback for unexpected format
                        product_dict['City'] = loc_date_tag.text
                        product_dict['Neighborhood'] = ''
                        product_dict['Datetime'] = ''
                else:
                    product_dict['City'] = ''
                    product_dict['Neighborhood'] = ''
                    product_dict['Datetime'] = '-'
                
                product_dict['State'] = state_map.get(self._state.lower(), self._state.upper())
                
                products_list.append(product_dict)

            page += 1

        return products_list
