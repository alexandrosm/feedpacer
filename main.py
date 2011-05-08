#!/usr/bin/env python

from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

import handlers

def main():
	application = webapp.WSGIApplication([
		('/', handlers.MainHandler),
		(r'/main/(?P<usernick>[^/]*)/', handlers.UserMainHandler),
		(r'/feeds/(?P<usernick>[^/]*)/new', handlers.NewFeedHandler),
		(r'/feeds/edit/(?P<user_id>\d+)/(?P<feed>.*)$', handlers.EditFeedHandler),
		(r'/feeds/(?P<user_id>\d+)/(?P<feed>.*)$', handlers.RenderFeedHandler),
		('/fpadmin/feeds/all', handlers.AllFeedsHandler)
		], debug=True)

	util.run_wsgi_app(application)

if __name__ == '__main__':
	main()
