import csv

# latitude grows south to north
# longitude grows west to east
regions = [{'slug': 'metro-boston-events',
            'north': 42.416126,
            'south': 42.255709,
            'west': -71.271331
            },
           {'slug': 'north-boston-suburbs-events',
            'north': 42.570831,
            'west': -71.271331,
            'south': 42.416126
            },
           {'slug': 'south-boston-suburbs-events',
            'south': 42.125123,
            'west': -71.271331,
            'north': 42.255709
            },
           {'slug': 'west-boston-suburbs-events',
            'west': -71.656497,
            'north': 42.570831,
            'south': 42.125123,
            'east': -71.271331
            },
           {'slug': 'cape-cod-events',
            'north': 41.771848,
            'west': -70.549556
            },
           {'slug': 'central-mass-events',
            'west': -72.512137,
            'east': -71.656497
            },
           {'slug': 'northern-mass',
            'west': -71.656497,
            'south': 42.570831
            },
           {'slug': 'southern-mass-events',
            'west': -71.656497,
            'north': 42.125123,
            'east': -70.549556
            },
           {'slug': 'western-mass-events',
            'east': -72.512137}
           ]


def get_ma_region(latitude, longitude):
    for region in regions:
        if 'west' in region and longitude < region['west']:
            continue
        if 'east' in region and longitude > region['east']:
            continue
        if 'south' in region and latitude < region['south']:
            continue
        if 'north' in region and latitude > region['north']:
            continue
        return region['slug']
    return None


def get_ma_region_by_location(location, city):
    if city == "Falmouth":
        # Falmouth defies a broad rectangular cape region, too far West
        return 'cape-cod-events'
    latitude = float(location['latitude'])
    longitude = float(location['longitude'])
    return get_ma_region(latitude, longitude)


def get_ma_region_by_zip(zip):
    latitude, longitude = get_location_from_zip(zip)
    if latitude is None:
        return None
    return get_ma_region(latitude, longitude)


zip_geo_data = None


def get_location_from_zip(zip):
    global zip_geo_data
    if zip_geo_data is None:
        load_zip_geo_data()
    if zip in zip_geo_data:
        return zip_geo_data[zip]
    return None, None


def load_zip_geo_data():
    global zip_geo_data
    zip_geo_data = {}
    with open('us-zip-code-latitude-and-longitude.csv') as ifile:
        reader = csv.reader(ifile)
        in_headers = next(reader)
        for record in reader:
            zip_geo_data['0' + record[0]] = (float(record[1]), float(record[2]))


