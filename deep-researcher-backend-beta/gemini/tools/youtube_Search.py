from py_youtube import Search
import json

videos = Search("manhunt minecraft").videos()
print(json.dumps(videos, indent=2))