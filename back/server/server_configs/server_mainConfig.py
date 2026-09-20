# ! back/server/server_configs/server_mainConfig.py
# значения берутся из .env (settings.py), локальные конфиги больше не правим руками
from back.server.server_configs.settings import settings as _s

MONGO_URI = _s.mongo_uri
MONGO_CLUSTER = _s.mongo_cluster
MONGO_LMSCLUSTER = _s.mongo_lmscluster
MONGO_LMSLESSONS = _s.mongo_lmslessons
MONGO_LMSCOURSESDATA = _s.mongo_lmscoursesdata
MONGO_LMSPROGRESS = _s.mongo_lmsprogress
MONGO_LMSTASKS = _s.mongo_lmstasks
MONGO_LMSTESTS = _s.mongo_lmstests
MONGO_USERS = _s.mongo_users
