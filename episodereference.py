# -*- coding: utf-8 -*-
# Make sure you rename config.py.example to config.py and fill it out before trying to run this!
# Get our config variables.
import config
# Used to be a nice API user. Max 240 req/min.
from time import sleep
# Used to talk to the wikidot API.
from xmlrpclib import ServerProxy
# Used to work with the local database of works covered.
import sqlite3
# used to check arguments for performing various jobs
from sys import argv

# All functions will involve the database, let's prep our connection.
conn = sqlite3.connect('cafe.db')
conn.text_factory = str
db = conn.cursor()

# Let's also make our connection to Wikidot.
s = ServerProxy('https://' + config.wikidot_username + ':' + config.wikidot_api_key + "@www.wikidot.com/xml-rpc-api.php")


if "--prepdb" in argv:
    # Create our tables.
    db.execute('''CREATE TABLE articles
    (id INTEGER PRIMARY KEY ASC,
    slug TEXT NOT NULL,
    title TEXT NOT NULL,
    authors TEXT NOT NULL,
    content TEXT NOT NULL,
    flags INTEGER)''')
    db.execute('''CREATE TABLE shows
    (id INTEGER PRIMARY KEY ASC,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    excerpt TEXT)''')
    db.execute('''CREATE TABLE appearances
    (id INTEGER PRIMARY KEY ASC,
    show_id INTEGER NOT NULL,
    article_id INTEGER NOT NULL,
    flags INTEGER)''')

if "--newshow" in argv:
# if len(argv) == 1:
    showtitle = raw_input("Show title: ")
    showurl = raw_input("Show URL: ")
    showexcerpt = raw_input("Show Excerpt: ")
    print "Adding show to DB."
    db.execute('INSERT INTO shows VALUES(NULL,?,?,?)', (showtitle, showurl, showexcerpt))
    conn.commit()
    print "Show added successfully."
    show_id = db.lastrowid
    slugs = raw_input("Slugs to retrieve for show, separated by commas with one trailing space: ")
    sluglist = slugs.split(", ")
    for article in sluglist:
        # Get the actual page content and full metadata set.
        print "Pulling " + article
        page = s.pages.get_one({"site": config.wikidot_site, "page": article})
        # Obey the speed limit.
        sleep(0.25)
        flags = input("Article Flags (0 for none, 1 for first-timer, 2 for selection, 3 for both): ")
        # We're going to put this both in the sqlite database and the Cafe archive.
        print "Adding " + article + " to articles table."
        try:
            db.execute('INSERT INTO articles VALUES(NULL,?,?,?,?,?)',
                       (page["fullname"], page["title_shown"], page["created_by"], page["content"], flags))
        except sqlite3.IntegrityError:
            newauthor = raw_input("Author has deleted their account. Please provide their username: ")
            db.execute('INSERT INTO articles VALUES(NULL,?,?,?,?,?)',
                       (page["fullname"], page["title_shown"], newauthor, page["content"], flags))
        conn.commit()
        article_id = db.lastrowid
        appearances = [(show_id, article_id)]
        print "Associating " + article + " to show."
        db.execute('INSERT INTO appearances VALUES(NULL,?,?,NULL)', (show_id, article_id))
        conn.commit()
    if "--noupload" not in argv:
        for article in sluglist:
            # Now, to stick in the Cafe archive.
            # Correct workflow is create the page, then import the files.
            page = s.pages.get_one({"site": config.wikidot_site, "page": article})
            # Obey the speed limit.
            sleep(0.25)
            print "Saving page to wikidot."
            page["tags"].append('_archived-article')
            newpage = s.pages.save_one({"site": config.cafe_site, "page": page["fullname"], "title": page["title_shown"], "content": page["content"], "tags": page["tags"]})
            sleep(0.25)
            print "Getting list of files associated with " + article + "."
            oldfiles = s.files.select({"site": config.wikidot_site, "page": page["fullname"]})
            sleep(0.25)
            for filename in oldfiles:
                try:
                    print "Getting " + filename + "."
                except UnicodeEncodeError:
                    pass
                attachment = s.files.get_one({"site": config.wikidot_site, "page": page["fullname"], "file": filename})
                sleep(0.25)
                try:
                    print "Uploading " + filename + " to cafe wiki."
                except UnicodeEncodeError:
                    pass
                upload = s.files.save_one({"site": config.cafe_site, "page": page["fullname"], "file": filename,"content": attachment["content"], "comment": attachment["comment"], "revision_comment": "Uploaded with cafetools."})
                sleep(0.25)

def output():
    w = open("wikidot.txt","w+")
    w.write("")
    w.close()
    w = open("wikidot.txt", "a")

    h = open("html.txt", "w+")
    h.write("")
    h.close()
    h = open("html.txt", "a")

    appearances = conn.execute("SELECT * FROM appearances JOIN shows on shows.id = appearances.show_id JOIN articles on articles.id = appearances.article_id ORDER BY shows.url")
    wikidotoutput = ""
    htmloutput = ""

    w.write("//**NOTE:**// † indicates author's first positive-rated article. ¤ indicates bluesoul's personal favorites\n\n||~ Episode ||~ Article ||~ Author ||\n")
    h.write("<table class='wp-block-table tablesorter'><thead><tr><th>Episode ↕</th><th>Article ↕</th><th>Author ↕</th></tr></thead><tbody>")

    for row in appearances.fetchall():
        w.write("||[*" + row[6] + " " + row[5] + "]||[*http://scp-wiki.net/" + row[9] + " " + row[10] + "] ([*http://scpcafe.wikidot.com/" + row[9] + " Archive])")
        if row[13] is 1:
            w.write(" †")
        elif row[13] is 2:
            w.write(" ¤")
        elif row[13] is 3:
            w.write(" †¤")
        w.write("||[[*user " + row[11] + "]]||\n")
        h.write("<tr><td><a href='" + row[6] + "' target='_blank' rel='noreferrer noopener' aria-label='" + row[5] + " (opens in a new tab)'>" + row[5] + "</a></td><td><a href='http://www.scp-wiki.net/" + row[9] + "' target='_blank' rel='noreferrer noopener' aria-label='" + row[10] + "(opens in a new tab)'>" + row[10] + "</a> (<a href='http://scpcafe.wikidot.com/" + row[9] + "'>Archive</a>)")
        if row[13] is 1:
            h.write(" †")
        elif row[13] is 2:
            h.write(" ¤")
        elif row[13] is 3:
            h.write(" †¤")
        h.write("</td><td>" + row[11] + "</td></tr>")

    h.write("</tbody></table>")

    # Upload to wikidot.
    w.close()
    w = open("wikidot.txt", "r")
    wstr = w.read()
    updatereference = s.pages.save_one({"site": config.cafe_site, "page": "episode-reference", "title": "Episode Reference", "content": wstr})

if "--output" in argv:
    output()
