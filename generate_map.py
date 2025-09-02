import requests
import xml.etree.ElementTree as ET
import json
import os
import glob
from datetime import datetime
from bs4 import BeautifulSoup

# URL base para descargar los XML
BASE_URL = "https://infocar.dgt.es/datex2/v3/dgt/zbe/ControledZonePublication/"
OUTPUT_DIR = "data"
GEOJSON_FILE = "low_emission_zones.geojson"

def fetch_xml_urls():
    """Fetches the list of XML file URLs by parsing the HTML of the DGT's index page."""
    try:
        response = requests.get(BASE_URL)
        response.raise_for_status()
        
        # Use BeautifulSoup to parse the HTML and find all links
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a')
        
        xml_urls = []
        for link in links:
            href = link.get('href')
            if href and href.endswith('.xml'):
                xml_urls.append(BASE_URL + href)
        
        return xml_urls
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the XML URL list: {e}")
        return []

def process_xml_to_geojson(xml_urls):
    """Processes XML files and converts them into a GeoJSON structure."""
    geojson_features = []
    print(f"Found {len(xml_urls)} XML files to process.")

    for url in xml_urls:
        try:
            response = requests.get(url)
            response.raise_for_status()
            root = ET.fromstring(response.content)

            # Define namespaces
            ns = {
                'conz': 'http://levelC/schema/3/controlledZone',
                'com': 'http://levelC/schema/3/common',
                'tra': 'http://levelC/schema/3/trafficRegulation',
                'loc': 'http://levelC/schema/3/locationReferencing'
            }

            # Find all controlled zones
            for zone in root.findall('.//conz:controlledZone', ns):
                zone_name_elem = zone.find('.//conz:name/com:values/com:value', ns)
                zone_name = zone_name_elem.text if zone_name_elem is not None else "Unknown Zone"
                
                # Find all polygon coordinates for the zone
                polygons = []
                for polygon in zone.findall('.//loc:openlrPolygonCorners', ns):
                    coords = []
                    for coord in polygon.findall('loc:openlrCoordinates', ns):
                        lat = float(coord.find('loc:latitude', ns).text)
                        lon = float(coord.find('loc:longitude', ns).text)
                        coords.append([lon, lat])
                    # GeoJSON requires the first and last coordinate to be the same to close the polygon
                    if coords and coords[0] != coords[-1]:
                        coords.append(coords[0])
                    polygons.append(coords)

                if polygons:
                    # Create a GeoJSON Feature for the zone
                    feature = {
                        "type": "Feature",
                        "properties": {
                            "name": zone_name
                        },
                        "geometry": {
                            "type": "MultiPolygon",
                            "coordinates": [polygons]
                        }
                    }
                    geojson_features.append(feature)
        
        except requests.exceptions.RequestException as e:
            print(f"Error fetching XML file from {url}: {e}")
        except ET.ParseError as e:
            print(f"Error parsing XML from {url}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred processing {url}: {e}")
            
    return {
        "type": "FeatureCollection",
        "features": geojson_features
    }

def save_geojson(data, filename):
    """Saves the GeoJSON data to a file."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"Successfully saved GeoJSON data to {filepath}")

def clean_old_files():
    """Removes old XML files if any exist."""
    files = glob.glob(os.path.join(OUTPUT_DIR, '*.xml'))
    for f in files:
        os.remove(f)
    print(f"Cleaned up old XML files.")

if __name__ == "__main__":
    print(f"Starting data update at {datetime.now()}...")
    clean_old_files() # Clean up old files before fetching new ones
    
    xml_urls = fetch_xml_urls()
    if xml_urls:
        geojson_data = process_xml_to_geojson(xml_urls)
        if geojson_data['features']:
            save_geojson(geojson_data, GEOJSON_FILE)
        else:
            print("No features were processed. GeoJSON file was not created.")
    else:
        print("No XML files found to process. Exiting.")
    print(f"Data update finished at {datetime.now()}.")
