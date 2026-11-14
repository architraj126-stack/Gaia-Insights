"""
Bundle Natural Earth admin-0 (countries) and admin-1 (states/provinces) boundaries.
Downloads authoritative Natural Earth cultural vectors, extracts and cleans geometries,
simplifies appropriately for web display and regional queries, and stores them as GeoJSON.
"""
import io
import json
import os
import re
import tempfile
import urllib.request
import zipfile
import geopandas as gpd
from shapely.geometry import mapping

BOUNDARIES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "boundaries")
os.makedirs(BOUNDARIES_DIR, exist_ok=True)

URL_ADMIN_0 = "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip"
URL_ADMIN_1 = "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_1_states_provinces.zip"

def slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", str(text)).strip().lower()
    return re.sub(r"[-\s]+", "_", s)

def download_and_extract(url: str, extract_to: str):
    print(f"Downloading {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "EarthScienceExplorer/1.0"})
    with urllib.request.urlopen(req) as resp:
        content = resp.read()
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        z.extractall(extract_to)
    print(f"Extracted to {extract_to}")

def process_admin_0():
    print("Processing Admin-0 Countries...")
    with tempfile.TemporaryDirectory() as td:
        download_and_extract(URL_ADMIN_0, td)
        shp_path = os.path.join(td, "ne_110m_admin_0_countries.shp")
        gdf = gpd.read_file(shp_path)

        features = []
        for _, row in gdf.iterrows():
            name = row.get("NAME") or row.get("ADMIN") or "Unknown"
            admin = row.get("ADMIN") or name
            iso_a3 = row.get("ISO_A3") or row.get("ADM0_A3") or "UNK"
            if iso_a3 == "-99" or not iso_a3:
                iso_a3 = slugify(name)[:3].upper()
            region_id = f"admin0_{slugify(iso_a3)}_{slugify(name)}"
            
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            
            # Bounds
            minx, miny, maxx, maxy = geom.bounds
            
            features.append({
                "type": "Feature",
                "id": region_id,
                "properties": {
                    "id": region_id,
                    "name": str(name),
                    "admin": str(admin),
                    "iso_a3": str(iso_a3),
                    "type": "admin-0",
                    "subtype": "country",
                    "continent": str(row.get("CONTINENT") or ""),
                    "bbox": [round(minx, 5), round(miny, 5), round(maxx, 5), round(maxy, 5)]
                },
                "geometry": json.loads(json.dumps(mapping(geom)))
            })

        fc = {
            "type": "FeatureCollection",
            "name": "natural_earth_admin_0_countries",
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
            "features": features
        }
        out_path = os.path.join(BOUNDARIES_DIR, "admin_0.geojson")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(fc, f)
        print(f"Saved {len(features)} admin-0 features to {out_path} ({os.path.getsize(out_path) / 1024:.1f} KB)")

def process_admin_1():
    print("Processing Admin-1 States/Provinces...")
    with tempfile.TemporaryDirectory() as td:
        download_and_extract(URL_ADMIN_1, td)
        shp_path = os.path.join(td, "ne_10m_admin_1_states_provinces.shp")
        gdf = gpd.read_file(shp_path)

        # Simplify geometry with preserve_topology=True to keep payload reasonable
        print(f"Simplifying {len(gdf)} admin-1 polygons...")
        gdf["geometry"] = gdf["geometry"].simplify(0.04, preserve_topology=True)

        features = []
        for idx, row in gdf.iterrows():
            name = row.get("name") or row.get("name_en") or "Unknown"
            name_en = row.get("name_en") or name
            admin = row.get("admin") or "Unknown"
            adm0_a3 = row.get("adm0_a3") or "UNK"
            type_en = row.get("type_en") or "State/Province"
            
            slug_country = slugify(adm0_a3)
            slug_name = slugify(name_en)
            region_id = f"admin1_{slug_country}_{slug_name}_{idx}"
            
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue

            minx, miny, maxx, maxy = geom.bounds

            features.append({
                "type": "Feature",
                "id": region_id,
                "properties": {
                    "id": region_id,
                    "name": str(name_en),
                    "local_name": str(name),
                    "country": str(admin),
                    "adm0_a3": str(adm0_a3),
                    "type": "admin-1",
                    "subtype": str(type_en),
                    "bbox": [round(minx, 5), round(miny, 5), round(maxx, 5), round(maxy, 5)]
                },
                "geometry": json.loads(json.dumps(mapping(geom)))
            })

        fc = {
            "type": "FeatureCollection",
            "name": "natural_earth_admin_1_states_provinces",
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
            "features": features
        }
        out_path = os.path.join(BOUNDARIES_DIR, "admin_1.geojson")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(fc, f)
        print(f"Saved {len(features)} admin-1 features to {out_path} ({os.path.getsize(out_path) / 1024 / 1024:.2f} MB)")

def create_license():
    license_content = """# Natural Earth Boundary Data Licence and Attribution

## Source
- Dataset: Natural Earth Vector (Admin 0 - Countries, Admin 1 - States and Provinces)
- Provider: Natural Earth (https://www.naturalearthdata.com/)
- Versions: 110m Admin-0 Countries, 10m Admin-1 States/Provinces (simplified for regional analysis)

## Licence
Natural Earth vector map data is in the **Public Domain**.
All versions of Natural Earth raster and vector map data made available on the naturalearthdata.com website are in the public domain. You may use the maps in any manner, including modifying the content and designs, creating derivative works, and commercial use, without restriction.

## Attribution
"Made with Natural Earth. Free vector and raster map data @ naturalearthdata.com."

Terms of Use: https://www.naturalearthdata.com/about/terms-of-use/
"""
    lic_path = os.path.join(BOUNDARIES_DIR, "LICENSE.md")
    with open(lic_path, "w", encoding="utf-8") as f:
        f.write(license_content)
    print(f"Saved licence and attribution to {lic_path}")

if __name__ == "__main__":
    process_admin_0()
    process_admin_1()
    create_license()
