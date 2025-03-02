import os
from datetime import UTC, datetime, timedelta
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

_HEARTBEAT_FILE: Path = Path().cwd() / "translations_heartbeat.txt"


def _write_heartbeat() -> None:
    """Writes to a file that is used as health check in docker"""
    print("Writing TRANSLATION-BEAT to file")
    with _HEARTBEAT_FILE.open("w") as f:
        f.write(str(datetime.now(tz=UTC)))


def _check_heartbeat() -> bool:
    if not _HEARTBEAT_FILE.exists():
        return True

    with _HEARTBEAT_FILE.open("r") as f:
        last_time: datetime = datetime(f.read(), tzinfo=UTC)
        if datetime.now(tz=UTC) - last_time > timedelta(hours=3):
            return True

    return False


def can_be_translated(date: str) -> bool:
    """Checks if given item is old enough to be considered for auto translation"""
    return datetime.now() - datetime.strptime(date, "%m/%d/%y %H:%M:%S") > timedelta(  # noqa: DTZ007, DTZ005
        days=2,
    )


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
        if response.status_code != 204:  # noqa: PLR2004
            print("Failed to translate subtitle")
        else:
            print("Success translating subtitle")
    except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout):
        pass


def translate_movies() -> None:
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
                    for action in item_info["data"]:
                        if (
                            action["action"] == 1
                            and action["language"]["code2"] == SECOND_LANG.lower()
                        ):  # downloaded subtitles
                            print(
                                f"Subtitles for {SECOND_LANG} downloaded on {action['parsed_timestamp']}",
                            )
                            if not can_be_translated(action["parsed_timestamp"]):
                                print("Not eligible for translation")
                                continue
                            translate_subtitle(
                                action["subtitles_path"],
                                action["radarrId"],
                                "movie",
                            )
                            break

        else:
            print("Nothing to do - movies")


def translate_series() -> None:
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
                for action in item_info["data"]:
                    if (
                        action["action"] == 1
                        and action["language"]["code2"] == SECOND_LANG.lower()
                    ):  # downloaded subtitles
                        print(
                            f"Subtitles for {SECOND_LANG} downloaded on {action['parsed_timestamp']}",
                        )
                        if not can_be_translated(action["parsed_timestamp"]):
                            print("Not eligible for translation")
                            continue
                        translate_subtitle(
                            action["subtitles_path"],
                            action["sonarrEpisodeId"],
                            "episode",
                        )
                        break
        else:
            print("Nothing to do - series")


def translate_bazarr() -> None:
    if not AUTO_TRANSLATE:
        return
    if not _check_heartbeat():
        return

    translate_movies()
    translate_series()
    _write_heartbeat()


def main() -> None:
    translate_movies()
    translate_series()


if __name__ == "__main__":
    main()
