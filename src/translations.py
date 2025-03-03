import os
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

FIRST_LANG = os.getenv("FIRST_LANG")
SECOND_LANG = os.getenv("SECOND_LANG")
BAZARR_HOSTNAME = os.getenv("BAZARR_HOSTNAME")
BAZARR_PORT = os.getenv("BAZARR_PORT")
BAZARR_APIKEY = os.getenv("BAZARR_APIKEY")
HEADERS = {"Accept": "application/json", "X-API-KEY": BAZARR_APIKEY}
AUTO_TRANSLATE = os.getenv("AUTO_TRANSLATE")

# ruff: noqa: T201

def can_be_translated(date: str) -> bool:
    """Checks if given item is old enough to be considered for auto translation"""
    return datetime.now() - date > timedelta(days=2)  # noqa: DTZ005


def translate_subtitle(path_to_existing_sub: str, item_id: str, item_type: str) -> None:
    try:
        print(f"Translating {path_to_existing_sub}")
        response = requests.patch(
            url=f"http://{BAZARR_HOSTNAME}:{BAZARR_PORT}/api/subtitles",
            timeout=600,
            headers=HEADERS,
            params={
                "action": "translate",
                "language": str(FIRST_LANG).lower(),
                "path": path_to_existing_sub,
                "type": item_type,
                "id": item_id,
                "original_format": True,
            },
        )
        print(f"Status code : {response.status_code}")
        print(f"Data: {response.text}")
        if response.status_code != 204:  # noqa: PLR2004
            print("Failed to translate subtitle")
        else:
            print("Success translating subtitle")
    except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout):
        pass


def translate_movies() -> None:  # noqa: C901
    wanted = requests.get(
        f"http://{BAZARR_HOSTNAME}:{BAZARR_PORT}/api/movies/wanted?start=0&length=-1",
        headers=HEADERS,
        timeout=60,
    )
    if wanted.status_code == requests.codes.OK:
        wanted_movies = wanted.json()
        if wanted_movies["total"] > 0:
            for movie in wanted_movies["data"]:
                for missing_subtitle in movie["missing_subtitles"]:
                    if missing_subtitle["code2"] != FIRST_LANG.lower():
                        continue
                    print(
                        f"Missing subtitles for {movie['title']}, {movie["radarrId"]=}",
                    )
                    # check if movie already has second language subtitles downloaded
                    item_info = requests.get(
                        url=f"http://{BAZARR_HOSTNAME}:{BAZARR_PORT}/api/movies/history",
                        headers=HEADERS,
                        params={
                            "start": 0,
                            "length": -1,
                            "radarrid": movie["radarrId"],
                        },
                        timeout=60,
                    )
                    if item_info.status_code != requests.codes.OK:
                        print(f"Failed to fetch data for {movie['title']}")
                        continue
                    item_info = item_info.json()

                    most_recent_timestamp = None
                    most_recent_subtitle_path = None
                    most_recent_radarr_id = None

                    for action in item_info["data"]:
                        if action["action"] in (1, 3) and action["language"]["code2"] == SECOND_LANG.lower():
                            print(f"Subtitles for {SECOND_LANG} downloaded on {action['parsed_timestamp']}")

                            current_timestamp = datetime.strptime(action["parsed_timestamp"], "%m/%d/%y %H:%M:%S")  # noqa: DTZ007
                            # Update most recent if this is the first eligible one or if it's newer
                            if most_recent_timestamp is None or current_timestamp > most_recent_timestamp:
                                most_recent_timestamp = current_timestamp
                                most_recent_subtitle_path = action["subtitles_path"]
                                most_recent_radarr_id = action["radarrId"]

                    if most_recent_timestamp and can_be_translated(most_recent_timestamp):
                        translate_subtitle(
                            most_recent_subtitle_path,
                            most_recent_radarr_id,
                            "movie",
                        )
                    else:
                        print("Not eligible for translation")
        else:
            print("Nothing to do - movies")


def translate_series() -> None:  # noqa: C901
    wanted = requests.get(
        f"http://{BAZARR_HOSTNAME}:{BAZARR_PORT}/api/episodes/wanted?start=0&length=-1",
        headers=HEADERS,
        timeout=60,
    )
    if wanted.status_code == requests.codes.OK:
        wanted_episodes = wanted.json()
        if wanted_episodes["total"] > 0:
            for episode in wanted_episodes["data"]:
                for missing_subtitle in episode["missing_subtitles"]:
                    if missing_subtitle["code2"] != FIRST_LANG.lower():
                        continue
                print(
                    f"Missing subtitles for {episode['seriesTitle']} - {episode['episodeTitle']}, {episode["sonarrEpisodeId"]=}",
                )
                # check if episode already has second language subtitles downloaded
                item_info = requests.get(
                    url=f"http://{BAZARR_HOSTNAME}:{BAZARR_PORT}/api/episodes/history",
                    headers=HEADERS,
                    params={
                        "start": 0,
                        "length": -1,
                        "episodeid": episode["sonarrEpisodeId"],
                    },
                    timeout=120,
                )
                if item_info.status_code != requests.codes.OK:
                    print(f"Failed to fetch data for {episode['episodeTitle']}")
                    continue

                item_info = item_info.json()

                most_recent_timestamp = None
                most_recent_subtitle_path = None
                most_recent_sonarr_id = None

                for action in item_info["data"]:
                    if action["action"] in (1, 3) and action["language"]["code2"] == SECOND_LANG.lower():
                        print(f"Subtitles for {SECOND_LANG} downloaded on {action['parsed_timestamp']}")

                        current_timestamp = datetime.strptime(action["parsed_timestamp"], "%m/%d/%y %H:%M:%S")  # noqa: DTZ007
                        # Update most recent if this is the first eligible one or if it's newer
                        if most_recent_timestamp is None or current_timestamp > most_recent_timestamp:
                            most_recent_timestamp = current_timestamp
                            most_recent_subtitle_path = action["subtitles_path"]
                            most_recent_sonarr_id = action["sonarrEpisodeId"]

                if most_recent_timestamp and can_be_translated(most_recent_timestamp):
                    translate_subtitle(
                        most_recent_subtitle_path,
                        most_recent_sonarr_id,
                        "episode",
                    )
        else:
            print("Nothing to do - series")


def main() -> None:
    translate_movies()
    translate_series()


if __name__ == "__main__":
    main()
