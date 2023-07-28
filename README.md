# kubra
Scraper of storm outage data from kubra.io

To install:

```console
> pip install kubra
```

To use:

```console
>  kubra --help
Usage: kubra [OPTIONS] INSTANCE_ID VIEW_ID

  Download all the outages of a storm event associated with an INSTANCE_ID and
  VIEW_ID from kubra.io. Outputs a JSON array of outages.

  Note that the geometries are encoded as Google polylines.

  To find values for INSTANCE_ID and VIEW_ID, go to the outage website, open
  up Developer Tools and look for a network request that looks like:

  https://kubra.io/stormcenter/api/v1/stormcenters/4fbb3ad3-e01d-4d71-9575-d45
  3769c1171/views/8ed2824a-bd92-474e-a7c4-848b812b7f9b/currentState?preview=fa
  lse

  The first GUID (i.e. 4fbb3ad3-e01d-4d71-9575-d453769c1171) is the
  INSTANCE_ID. The second GUID (i.e. 8ed2824a-bd92-474e-a7c4-848b812b7f9b) is
  the VIEW_ID.

Options:
  --cache_dir TEXT  Directory to use to cache responses
  --help            Show this message and exit.
```
