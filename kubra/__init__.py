import functools
import json

import click
import mercantile
import polyline
import scrapelib
import tqdm


class KubraScraper(scrapelib.Scraper):
    base_url = "https://kubra.io"
    MIN_ZOOM = 7
    MAX_ZOOM = 14

    def __init__(self, instance_id=None, view_id=None, **kwargs):
        super().__init__(**kwargs)
        self.instance_id = instance_id
        self.view_id = view_id

    @functools.cached_property
    def _state(self):

        state_url = f"{self.base_url}/stormcenter/api/v1/stormcenters/{self.instance_id}/views/{self.view_id}/currentState?preview=false"
        response = self.get(state_url)

        return response.json()

    @functools.cached_property
    def _cluster_url_template(self):
        deploymentId = self._state["stormcenterDeploymentId"]
        config_url = f"{self.base_url}/stormcenter/api/v1/stormcenters/{self.instance_id}/views/{self.view_id}/configuration/{deploymentId}?preview=false"

        config = self.get(config_url).json()
        interval_data = config["config"]["layers"]["data"]["interval_generation_data"]
        (layer,) = [
            layer
            for layer in interval_data
            if layer["type"].startswith("CLUSTER_LAYER")
        ]

        data_path = self._state["data"]["cluster_interval_generation_data"]
        return f"{self.base_url}/{data_path}/public/{layer['id']}/{{quadkey}}.json"

    def expected_outages(self):
        data_path = self._state["data"]["interval_generation_data"]
        data_url = f"{self.base_url}/{data_path}/public/summary-1/data.json"
        data = self.get(data_url).json()
        return data["summaryFileData"]["totals"][0]["total_outages"]

    def scrape(self):

        expected_outages = self.expected_outages()

        with tqdm.tqdm(total=expected_outages) as pbar:

            quadkeys = self._get_service_area_quadkeys()
            for response in self.descend(quadkeys):
                data = response.json()
                for outage in data["file_data"]:
                    outage["source"] = response.url
                    yield outage
                    pbar.update(outage["desc"]["n_out"])

    def descend(self, quadkeys):
        for quadkey in quadkeys:
            url = self._cluster_url_template.format(
                qkh=quadkey[-3:][::-1], quadkey=quadkey
            )
            response = self.get(url)
            if response.ok:
                any_clusters = any(
                    outage["desc"]["cluster"] for outage in response.json()["file_data"]
                )
                if not any_clusters or len(quadkey) == self.MAX_ZOOM:
                    yield response
                else:
                    yield from self.descend([quadkey + str(i) for i in (0, 1, 2, 3)])

    def _get_service_area_quadkeys(self):
        """Get the quadkeys for the entire service area"""

        ((regions_key, regions),) = self._state["datastatic"].items()
        service_areas_url = f"{self.base_url}/{regions}/{regions_key}/serviceareas.json"

        res = self.get(service_areas_url).json()
        areas = res.get("file_data")[0].get("geom").get("a")

        points = []
        for geom in areas:
            points += polyline.decode(geom)

        bbox = self._get_bounding_box(points)

        return [
            mercantile.quadkey(t)
            for t in mercantile.tiles(*bbox, zooms=[self.MIN_ZOOM])
        ]

    @staticmethod
    def _get_bounding_box(points):
        x_coordinates, y_coordinates = zip(*points)
        return [
            min(y_coordinates),
            min(x_coordinates),
            max(y_coordinates),
            max(x_coordinates),
        ]

    def accept_response(self, response, **kwargs):
        return response.status_code < 400 or response.status_code == 404


@click.command()
@click.argument("instance_id", type=str)
@click.argument("view_id", type=str)
@click.option("--cache_dir", type=str, help="Directory to use to cache responses")
def main(instance_id, view_id, cache_dir):
    """
    Download all the outages of a storm event associated with an INSTANCE_ID and VIEW_ID from kubra.io. Outputs a JSON array of outages.

    Note that the geometries are encoded as Google polylines.

    To find values for INSTANCE_ID and VIEW_ID, go to the outage website, open up Developer Tools and look for a network request that looks like:

    https://kubra.io/stormcenter/api/v1/stormcenters/4fbb3ad3-e01d-4d71-9575-d453769c1171/views/8ed2824a-bd92-474e-a7c4-848b812b7f9b/currentState?preview=false

    The first GUID (i.e. 4fbb3ad3-e01d-4d71-9575-d453769c1171) is the INSTANCE_ID. The second GUID (i.e. 8ed2824a-bd92-474e-a7c4-848b812b7f9b) is the VIEW_ID.
    """

    scraper = KubraScraper(
        instance_id,
        view_id,
        requests_per_minute=0,
    )

    if cache_dir:
        from scrapelib.cache import FileCache

        cache = FileCache(cache_dir)

        scraper.cache_storage = cache
        scraper.cache_write_only = False

    outages = list(scraper.scrape())
    click.echo(json.dumps(outages))
