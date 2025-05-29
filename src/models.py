from src import db
from datetime import datetime

class Task(db.Model):
    __tablename__ = 'userdetails'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password = db.Column(db.String, nullable=False)


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('userdetails.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('userdetails.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('Task', foreign_keys=[sender_id], backref=db.backref('sent_messages', lazy=True))
    receiver = db.relationship('Task', foreign_keys=[receiver_id], backref=db.backref('received_messages', lazy=True))


class UserData(db.Model):
    __tablename__ = 'userdata'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_auth_id = db.Column(db.Integer, db.ForeignKey('userdetails.id'), nullable=False)
    firstname = db.Column(db.String(255))
    lastname = db.Column(db.String(255))
    email = db.Column(db.String(200))
    gender = db.Column(db.String(50))
    hobbies = db.Column(db.ARRAY(db.String))
    preferences = db.Column(db.ARRAY(db.String))
    phone_number = db.Column(db.String(50))
    age = db.Column(db.String(10))
    bio = db.Column(db.Text)

    user = db.relationship('Task', backref=db.backref('user_data', lazy=True))


class RelationshipData(db.Model):
    __tablename__ = 'relationshipData'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_auth_id = db.Column(db.Integer, db.ForeignKey('userdetails.id'), nullable=False)
    email = db.Column(db.String(200))
    lookingfor = db.Column(db.String(255))
    openfor = db.Column(db.String(255))

    user = db.relationship('Task', backref=db.backref('get_relationship_data', lazy=True))


class UserImages(db.Model):
    __tablename__ = 'userImage'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_auth_id = db.Column(db.Integer, db.ForeignKey('userdetails.id'), nullable=False)
    email = db.Column(db.String(200))  # Ensure this column exists
    imageString = db.Column(db.String())
    user = db.relationship('Task', backref=db.backref('user_image', lazy=True))


class UserPreference(db.Model):
    __tablename__ = 'user_preference'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('userdetails.id'), nullable=False)
    preferred_user_id = db.Column(db.Integer, db.ForeignKey('userdetails.id'), nullable=False)
    preference = db.Column(db.String(20), nullable=False)  # 'like', 'reject', 'save_later'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('Task', foreign_keys=[user_id], backref=db.backref('preferences', lazy=True))
    preferred_user = db.relationship('Task', foreign_keys=[preferred_user_id],
                                     backref=db.backref('preferred_by', lazy=True))


class Match(db.Model):
    __tablename__ = 'matches'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user1_id = db.Column(db.Integer, db.ForeignKey('userdetails.id'), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey('userdetails.id'), nullable=False)
    match_date = db.Column(db.DateTime, default=datetime.utcnow)
    visible_after = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'active', 'deleted'

    # Relationships
    user1 = db.relationship('Task', foreign_keys=[user1_id], backref=db.backref('matches_as_user1', lazy=True))
    user2 = db.relationship('Task', foreign_keys=[user2_id], backref=db.backref('matches_as_user2', lazy=True))
