#!/usr/bin/env python

import os

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

import urllib2
import xml.etree
import xml.etree.ElementTree as et
from datetime import datetime
from datetime import timedelta

import models
et._namespace_map["http://www.google.com/schemas/reader/atom/"] = "gr"
et._namespace_map["urn:atom-extension:indexing"] = "idx"
et._namespace_map["http://search.yahoo.com/mrss/"] = "media"

def render_template(template_loc, template_values, self):
	path = os.path.join(os.path.dirname(__file__), 'templates/%s' % (template_loc))
	self.response.out.write(template.render(path, template_values))

def updateFeed(self, feed):
	fetchFeedURI = ("http://www.google.com/reader/public/atom/feed/%s?n=1000&client=feedpacer" % feed.uri)
	try:
		result = urllib2.urlopen(fetchFeedURI)
	except urllib2.HTTPError:
		result = None
		#eventually push an error.
		return

	res = result.read()
	#self.response.out.write("feed retreived<br/>")
	feedtree = et.XML(res)
	#self.response.out.write(feedtree.attrib)
	feed.checkedForUpdates = datetime.now()
	entries = feedtree.findall('{http://www.w3.org/2005/Atom}entry')
	latestItemId = entries[0].find('{http://www.w3.org/2005/Atom}id').text
	#self.response.out.write("%s %s<br/>" % (latestItemId, feed.latestItemId))
	if feed.latestItemId != latestItemId:
		#self.response.out.write("getting new items<br/>")
		#go through entries, add to list till you find 
		newitems = []

		ns = u'{http://www.w3.org/2005/Atom}'
		nsl = len(ns)
		for item in entries:
			if item.find('{http://www.w3.org/2005/Atom}id').text != feed.latestItemId:
				feedItem = models.FeedItem()
				feedItem.feed = feed

				for elem in item.getiterator():
					if elem.tag.startswith(ns):
						elem.tag = elem.tag[nsl:]
				feedItem.whole = "<entry" + et.tostring(item)[100:]
			
				newitems.append(feedItem)
			else:
				break
		nextnum = feed.totalItems
		feed.totalItems += len(newitems)
		
		while newitems:
			#self.response.out.write("adding item<br/>")
			feedItem = newitems.pop()
			feedItem.num = nextnum
			nextnum += 1
			feedItem.put()
			
		feed.latestItemId = latestItemId
			
	feed.put()
	return

class MainHandler(webapp.RequestHandler):
	def get(self):
		user = users.get_current_user()
		self.response.headers['Content-Type'] = 'text/html'
        
		if user:
			self.redirect('/main/%s/' % user.nickname())
		else:
			template_values = {
				"login_url": users.create_login_url("/")
			}
			
			render_template('index.html', template_values, self)
			
class UserMainHandler(webapp.RequestHandler):
	def get(self, usernick):
		user = users.get_current_user()
		if user and (((user.nickname() == usernick) or users.is_current_user_admin())):
			ufeedlist = ''
			ufeeds = models.UserFeed.all().fetch(10)
			debug = ''
			#do we know this user?
			userProfileSet = models.UserProfile.all().filter('user =', user).fetch(1)
			if not userProfileSet:
				userProfile = models.UserProfile()
				userProfile.user = user
				userProfile.email = user.email()
				userProfile.nickname = user.nickname()
				userProfile.id = user.user_id()
				userProfile.federated_identity = user.federated_identity()
				userProfile.federated_provider = user.federated_provider()
				userProfile.put()
			else:
				userProfile = userProfileSet[0]
				
			debug = userProfile.id
			
			template_values = {
				"user_feeds": ufeeds,
				"user_nickname": user.nickname(),
				"user_id": user.user_id(),
				"logout_url": users.create_logout_url("/"),
				"debug": debug
			}
			
			render_template('usermain.html', template_values, self)

class NewFeedHandler(webapp.RequestHandler):
	def get(self, usernick):
		user = users.get_current_user()
		if (user.nickname() == usernick) or users.is_current_user_admin():
			render_template('add.html', {}, self)
		else:
			self.redirect('/')
			#eventually send to a -not authorized (401)- page			
  	
	def post(self, usernick):
		user = users.get_current_user()
		if (user.nickname() == usernick) or users.is_current_user_admin():
			source = self.request.get('source')
			interval = self.request.get('interval')
			#check if feed has '?' in it. raise error if yes. (right?)

			#check if feed already exists
			feedset = models.Feed().all().filter('uri = ', source).fetch(1)
			if not feedset:
				#max 1000 items, no questions asked.
				fetchFeedURI = ("http://www.google.com/reader/public/atom/feed/%s?n=1000&client=feedpacer" % source)
				try:
					result = urllib2.urlopen(fetchFeedURI)
				except urllib2.HTTPError:
					result = None
					#eventually push an error.
					self.redirect('/')
				else:
					res = result.read()
					feedtree = et.XML(res)
					#self.response.out.write(feedtree.attrib)
    				
					feed = models.Feed()
					link = feedtree.find('{http://www.w3.org/2005/Atom}link')
					#handle -feed not found- error.
					if link.attrib['rel']=='alternate': feed.alt = link.attrib['href']
					feed.uri = source
					feed.fetched = datetime.now()
					feed.title = feedtree.find('{http://www.w3.org/2005/Atom}title').text
					feed.updated = datetime.strptime(feedtree.find('{http://www.w3.org/2005/Atom}updated').text, 
																		"%Y-%m-%dT%H:%M:%SZ")
					atom_id = feedtree.find('{http://www.w3.org/2005/Atom}id').text
					feedlinks = feedtree.findall('{http://www.w3.org/2005/Atom}link')
					for link in feedlinks:
						if link.attrib['rel'] == 'self':
							feed.rel_self = link.attrib['href']
						elif link.attrib['rel'] == 'alternate':
							feed.rel_alt = link.attrib['href']
					subt = feedtree.find('{http://www.w3.org/2005/Atom}subtitle')
					feed.subtitle = subt.text if subt is not None else None
					feed.atom_id = 'tag:feedpacer.appspot.com' + atom_id[14:20] + atom_id[27:]
					feed.idx = feedtree.attrib['{urn:atom-extension:indexing}index']
					feed.dir = feedtree.attrib['{http://www.google.com/schemas/reader/atom/}dir']
					entries = feedtree.findall('{http://www.w3.org/2005/Atom}entry')
					feed.latestItemId = entries[0].find('{http://www.w3.org/2005/Atom}id').text
					feed.checkedForUpdates = datetime.now()
					feed.totalItems = len(entries)
					feed.put()
					
					ns = u'{http://www.w3.org/2005/Atom}'
					nsl = len(ns)
					entries.reverse()
					for i,item in enumerate(entries):
						feedItem = models.FeedItem()
						feedItem.feed = feed
						feedItem.num = i
						
						for elem in item.getiterator():
							if elem.tag.startswith(ns):
								elem.tag = elem.tag[nsl:]
						feedItem.whole = "<entry" + et.tostring(item)[100:]
						feedItem.put()
												
						'''atom_id = item.find('id').text
						atom_id = 'tag:feedpacer.appspot.com' + atom_id[14:20] + atom_id[27:]
						feedItem.atom_id = atom_id
						
						feedItem.title = item.find('{http://www.w3.org/2005/Atom}title').text
						feedItem.uri = item.find('{http://www.w3.org/2005/Atom}link').attrib['href']
						feedItem.published = datetime.strptime(item.find('{http://www.w3.org/2005/Atom}published').text, 
																		"%Y-%m-%dT%H:%M:%SZ")
						feedItem.updated = datetime.strptime(item.find('{http://www.w3.org/2005/Atom}updated').text, 
																		"%Y-%m-%dT%H:%M:%SZ")
						it_sum = item.find('{http://www.w3.org/2005/Atom}summary')
						it_cont = item.find('{http://www.w3.org/2005/Atom}content')
						if it_sum is not None:
							feedItem.summary = it_sum.text
						elif it_cont is not None:
							feedItem.summary = it_cont.text
						else:
							feedItem.summary = ""
						#self.response.out.write((i, it_sum, it_cont.text))
						#self.response.out.write(feedItem.summary)'''
			else:
				feed = feedset[0]
			
				#check if user is already registered for this feed
				ufset = models.UserFeed().all().filter('user = ', user).filter('feed = ', feed).count(1)
			
			if (not feedset) or (not ufset):
				uf = models.UserFeed()
				uf.user = user
				uf.feed = feed
				uf.interval = int(interval)
				uf.currentItem = 0
				uf.lastUpdated = datetime.now()
				uf.put()
				self.redirect('/')
			else:
				self.redirect('/')
				#eventually push an error 'already subscribed'.
		else:
			self.redirect('/')
			#self.response.set_status(401)
			#eventually send to a -not authorized (401)- page

class UpdateFeedHandler(webapp.RequestHandler):
	def get(self, feed_uri):
		feedset = models.Feed().all().filter('uri = ', urllib2.unquote(feed_uri)).fetch(1)
		if feedset:
			feed = feedset[0]
			updateFeed(self, feed)
			#self.redirect('/')
		else:
			self.response.set_status(404)
			self.response.out.write("(!404) Feed not found (%s)" % urllib2.unquote(feed_uri))

class EditFeedHandler(webapp.RequestHandler):
	def get(self, user_id, feed_uri):
		user = users.get_current_user()
		if user_id == user.user_id() or users.is_current_user_admin():
			#validate that feed exists
			feedset = models.Feed().all().filter('uri = ', urllib2.unquote(feed_uri)).fetch(1)
			if feedset:
				feed = feedset[0]
				#validate that user is subscribed to feed
				ufset = models.UserFeed().all().filter('user = ', user).filter('feed = ', feed).fetch(1)
				if ufset:
					user_feed = ufset[0]
					template_values = {"user_feed": user_feed}
					render_template('edit.html', template_values, self)
				else:
					self.response.set_status(404)
					self.response.out.write("User not registered for feed")
			else:
				self.response.set_status(404)
				self.response.out.write("(404) Feed not found (%s)" % feed_uri)
		else:
			self.response.set_status(404)
			self.response.out.write("User does not exist")

	def post(self, user_id, feed_uri):
		user = users.get_current_user()
		if user_id == user.user_id() or users.is_current_user_admin():
			#validate that feed exists
			feedset = models.Feed().all().filter('uri = ', urllib2.unquote(feed_uri)).fetch(1)
			if feedset:
				feed = feedset[0]
				#validate that user is subscribed to feed
				ufset = models.UserFeed().all().filter('user = ', user).filter('feed = ', feed).fetch(1)
				if ufset:
					user_feed = ufset[0]
					interval = self.request.get('interval')
					user_feed.interval = int(interval)
					user_feed.put()
					self.refdirect('/')
				else:
					self.response.out.write("User not registered for feed")
			else:
				self.response.out.write("Feed not found (%s)" % feed_uri)
		else:
			self.response.out.write("User does not exist")

class RenderFeedHandler(webapp.RequestHandler):
	def get(self, user_id, feed_uri):
		#user = users.get_current_user()
		#if user_id == user.user_id() or users.is_current_user_admin():
		#fetch the user from the user_id
		userProfileSet = models.UserProfile().all().filter('id = ', user_id).fetch(1)
		if userProfileSet:
			user = userProfileSet[0].user
			#validate that feed exists
			feed_uri = urllib2.unquote(feed_uri)
			if not feed_uri[:7] == 'http://': 
				feed_uri = 'http://' + feed_uri
			feedset = models.Feed().all().filter('uri = ', feed_uri).fetch(1)
			if feedset:
				feed = feedset[0]
				#validate that user is subscribed to feed
				ufset = models.UserFeed().all().filter('user = ', user).filter('feed = ', feed).fetch(1)
				if ufset:
					user_feed = ufset[0]
					
					#find if it's time to update the feed
					interval = timedelta(minutes = user_feed.interval)
					time_since_update = datetime.now() - user_feed.lastUpdated
					if time_since_update >= interval:
						if user_feed.currentItem < feed.totalItems-1:
							user_feed.currentItem += 1
							user_feed.lastUpdated = datetime.now()
							user_feed.put()
						else:
							#check if we can add new items to the feed.
							time_since_last_check = datetime.now() - feed.lastCheckedForUpdates
							wait_period = timedelta(days = 1)
							if time_since_last_check > wait_period:
								updateFeed(self, feed)
					
					#find which items should go in the feed
					feed_items = feed.items.filter('num = ', user_feed.currentItem).fetch(1)
					
					template_values = {
						"feed": feed,
						"feed_items": feed_items
					}
					
					self.response.headers['Content-Type'] = "text/xml; charset=utf-8"
					render_template("feed.xml", template_values, self)
				else:
					self.response.out.write("User not registered for feed (%s)" % feed_uri)
			else:
				self.response.out.write("Feed not found (%s)" % feed_uri)
		else:
			self.response.out.write("User does not exist")
			
	def post(self, user_id, feed_uri):
		user = users.get_current_user()
		if user_id == user.user_id() or users.is_current_user_admin():
			feedset = models.Feed().all().filter('uri = ', urllib2.unquote(feed_uri)).fetch(1)
			if feedset:
				feed = feedset[0]
				if self.request.get('_method') == "DELETE":
					ufset = models.UserFeed().all().filter('user = ', user).filter('feed = ', feed).fetch(1)
					if ufset:
						ufset[0].delete()						
						self.redirect('/') #could sent back to user's homepage directly - save a request
					else:
						self.response.out.write("User not registered for feed")
				else:
					self.response.out.write("Malformed Request")
			else:
				self.response.out.write("Feed not found (%s)" % feed_uri)
		else:
			self.response.out.write("Not authorised")
