
import json
import requests
import re

def get_appid(name):
    url = f"https://store.steampowered.com/api/storesearch/?term={name}&l=polish&cc=PL"
    response = requests.get(url)
    data = response.json()
    return data["items"][0]['id']

def get_game_tags(appid):
    url = f"https://steamspy.com/api.php?request=appdetails&appid={appid}"
    response = requests.get(url)
    data = response.json()
    return data.get("tags", {})

def tag_map(filename="games.txt"):
    gametags = {}
    name_exception_map = {
        "Call of duty zombies": "Call of Duty: Black Ops II"
    }
    with open(filename, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i < 0:
                continue
            game = line.strip()
            print(f"Processing: {game}")
            game = re.sub(r"\s*\(.*?\)", "", game)
            if game in name_exception_map:
                game_steam = name_exception_map[game]
                appid = get_appid(game_steam)
            else:
                appid = get_appid(game)
            tags = get_game_tags(appid)
            gametags[game] = tags

    return gametags

def save_gametags(games_filename="games.txt", output_filename="gametags.json"):
    gametags = tag_map(games_filename)
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(gametags, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    save_gametags()