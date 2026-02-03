zip_geo_data = None


def get_location_from_zip(zip_code):
    global zip_geo_data
    if zip_geo_data is None:
        load_zip_geo_data()
    if zip_code in zip_geo_data:
        return zip_geo_data[zip_code]
    return None, None


# This data file comes from https://gist.github.com/emastra
def load_zip_geo_data():
    global zip_geo_data
    zip_geo_data = {}
    with open('zipToCoords.txt', encoding='utf8') as ifile:
        for line in ifile.readlines():
            data = line.split(',')
            zip_geo_data[data[0]] = (data[1], data[2].strip())





