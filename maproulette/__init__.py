import os
from flask import Flask
from simplekv.fs import FilesystemStore
from flask_kvsession import KVSessionExtension
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from flask_sqlalchemy import SQLAlchemy
from os.path import join, expanduser
from flask_migrate import Migrate

# initialize server KV session store
if not os.path.exists('./sessiondata'):
    os.makedirs('./sessiondata')

session_store = FilesystemStore('./sessiondata')

# instantiate flask app
app = Flask(__name__,
            static_folder='static',
            template_folder='templates',
            static_url_path='/static')

# get configuration from a non-repo file specified
# in this envvar
try:
    app.config.from_envvar('MAPROULETTE_SETTINGS')
except Exception:
    # alternate config file location for local development
    app.config.from_pyfile(join(expanduser('~'), '.maproulette/config.py'))

# set up the ORM engine and database object
engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'],
                       convert_unicode=True)
Base = declarative_base()
db = SQLAlchemy(app)
migrate = Migrate(app, db)

if not app.debug:
    import logging
    logging.basicConfig(
        filename=app.config['LOGFILE'],
        level=app.config['LOGLEVEL'])

from maproulette import models, views, oauth, api

# connect flask app to server KV session store
KVSessionExtension(session_store, app)

# CLI commands

@app.cli.command()
def cleanpyc():
    """Removes all *.pyc files from the project folder"""
    clean_command = "find . -name *.pyc -delete".split()
    subprocess.call(clean_command)


@app.cli.command()
def dropdb():
    """Drops the database tables"""
    db.drop_all()


@app.cli.command()
def createdb():
    """Creates the database tables"""
    db.create_all()


@app.cli.command()
def createtestdata(challenges=10, tasks=100, users=10):
    """Creates test data in the database"""
    import uuid
    import random
    from maproulette import db
    from maproulette.models import User, Challenge, Task, TaskGeometry, Action
    from shapely.geometry import Point, LineString, box

    # statuses to use
    statuses = ['available',
                'skipped',
                'fixed',
                'deleted',
                'alreadyfixed',
                'falsepositive']

    # challenge default strings
    challenge_help_test = "Sample challenge *help* text"
    challenge_instruction_test = "Challenge instruction text"
    task_instruction_text = "Task instruction text"

    # delete old tasks and challenges
    db.session.query(TaskGeometry).delete()
    db.session.query(Action).delete()
    db.session.query(Task).delete()
    db.session.query(Challenge).delete()
    db.session.query(User).delete()
    db.session.commit()

    # create users
    for uid in range(int(users)):
        user = User()
        user.id = uid
        user.display_name = 'Test User {uid}'.format(uid=uid)
        db.session.add(user)
    db.session.commit()

    # create ten challenges
    for i in range(1, int(challenges) + 1):
        print("Generating Test Challenge #%d" % i)
        minx = -120
        maxx = -40
        miny = 20
        maxy = 50
        challengepoly = None
        slug = "test%d" % i
        title = "Test Challenge %d" % i
        challenge = Challenge(slug, title)
        challenge.difficulty = random.choice([1, 2, 3])
        challenge.active = True
        challenge.blurb = "This is test challenge number %d" % i
        challenge.description = "This describes challenge %d in detail" % i
        challenge.help = challenge_help_test
        challenge.instruction = challenge_instruction_test
        # have bounding boxes for all but the first two challenges.
        if i > 2:
            minx = random.randrange(-120, -40)
            miny = random.randrange(20, 50)
            maxx = minx + 1
            maxy = miny + 1
            challengepoly = box(minx, miny, maxx, maxy)
            print("\tChallenge has a bounding box of ", challengepoly)
            challenge.polygon = challengepoly
        db.session.add(challenge)

        # add some tasks to the challenge
        print("\tGenerating %i tasks for challenge %i" % (int(tasks), i))
        # generate NUM_TASKS random tasks
        for j in range(int(tasks)):
            # generate a unique identifier
            identifier = str(uuid.uuid4())
            # create two random points not too far apart
            task_geometries = []
            p1 = Point(
                random.randrange(minx, maxx) + random.random(),
                random.randrange(miny, maxy) + random.random())
            p2 = Point(
                p1.x + (random.random() * random.choice((1, -1)) * 0.01),
                p1.y + (random.random() * random.choice((1, -1)) * 0.01))
            # create a linestring connecting the two points
            # no constructor for linestring from points?
            l1 = LineString([(p1.x, p1.y), (p2.x, p2.y)])
            # add the first point and the linestring to the task's geometries
            task_geometries.append(TaskGeometry(p1))
            # set a linestring for every other challenge
            if not j % 2:
                task_geometries.append(TaskGeometry(l1))
            # instantiate the task and register it with challenge 'test'
            # Initialize a task with its challenge slug and persistent ID
            task = Task(challenge.slug, identifier, task_geometries)
            # because we are not using the API, we need to call set_location
            # explicitly to set the task's location
            task.set_location()
            # generate random string for the instruction
            task.instruction = task_instruction_text
            # set a status
            action = Action(random.choice(statuses),
                            user_id=random.choice(range(int(users))))
            task.append_action(action)
            # add the task to the session
            db.session.add(task)

    # commit the generated tasks and the challenge to the database.
    db.session.commit()


@app.cli.command()
def cleanstaletasks():

    from maproulette import db
    from maproulette.models import Task, Action
    from sqlalchemy.sql.functions import max
    from datetime import datetime, timedelta
    import pytz

    current_time = datetime.now(pytz.utc)
    stale_threshold = current_time - timedelta(hours=1)
    counter = 0

    for task in db.session.query(Task).filter(
        Task.status.in_(['assigned', 'editing'])).join(
        Task.actions).group_by(
            Task.identifier, Task.challenge_slug).having(max(Action.timestamp) < stale_threshold).all():
        task.append_action(Action("available"))
        db.session.add(task)
        print("setting task %s to available" % (task.identifier))
        counter += 1
    db.session.commit()
    print('done. %i tasks made available' % counter)


@app.cli.command()
def populatetasklocation():
    """This command populates the new location field for each task"""
    from maproulette import db
    from maproulette.models import Task, Challenge
    for challenge in db.session.query(Challenge):
        counter = 0
        for task in db.session.query(Task).filter_by(
                challenge_slug=challenge.slug):
            task.set_location()
            counter += 1
            # commit every 1000
            if not counter % 1000:
                db.session.commit()
        db.session.commit()
        print('done. Location for %i tasks in challenge %s set' %\
            (counter, challenge.title))


@app.cli.command()
def cleansessions():
    """Remove all stored sessions"""
    session_dir = './sessiondata'
    for f in os.listdir(session_dir):
        file_path = os.path.join(session_dir, f)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(e)