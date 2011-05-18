from google.appengine.ext import db
from google.appengine.api import users

class Feed(db.Model):
	uri = db.LinkProperty()
	atom_id = db.StringProperty()
	rel_alt = db.LinkProperty()
	fetched = db.DateTimeProperty()
	title = db.StringProperty()
	subtitle = db.StringProperty()
	alt = db.LinkProperty()
	updated = db.DateTimeProperty()
	checkedForUpdates = db.DateTimeProperty()
	latestItemId = db.StringProperty()
	totalItems = db.IntegerProperty()
	idx = db.StringProperty()
	dir = db.StringProperty()
	
class FeedItem(db.Model):
	whole = db.TextProperty()
	feed = db.ReferenceProperty(Feed, collection_name='items')
	num = db.IntegerProperty()
	#atom_id = db.StringProperty()
	#uri = db.LinkProperty()
	#title = db.StringProperty()
	#category = db.StringProperty()
	#published = db.DateTimeProperty()
	#updated = db.DateTimeProperty()
	#summary = db.TextProperty()
	#author = db.StringProperty()
	#source = db.StringProperty()

class UserFeed(db.Model):
	user = db.UserProperty()
	feed = db.ReferenceProperty(Feed, collection_name='users')
	interval = db.IntegerProperty()
	lastUpdated = db.DateTimeProperty()
	cache = db.TextProperty()
	currentItem = db.IntegerProperty()
	
class UserProfile(db.Model):
	user = db.UserProperty()
	id = db.StringProperty()
	nickname = db.StringProperty()
	email = db.EmailProperty()
	federated_identity = db.StringProperty()
	federated_provider = db.StringProperty()

