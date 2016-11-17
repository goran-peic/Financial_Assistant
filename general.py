from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from pandas import DataFrame
from re import search
import numpy as np


# app.config["SQLALCHEMY_DATABASE_URI"] = 'postgresql://postgres:1malizabac@localhost/myDB'
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = 'postgres://msxfcphdhrrtzh:-0ju6mMOrikn9BkyS6AchPr3d_@ec2-54-163-245-32.compute-1.amazonaws.com:5432/dbtrgfqrofvsvd'
app.config["SECRET_KEY"] = 'GiveMeABreak'
db = SQLAlchemy(app)


class User(db.Model):

    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    password = db.Column(db.String(120), unique=False)

    def __init__(self, username, password):
        self.username = username
        self.password = password

    def is_active(self):
        return True

    def get_id(self):
        return self.id

    def is_authenticated(self):
        return self.authenticated

    def is_anonymous(self):
        return False

    def __repr__(self):
        return self.username

class Categories(db.Model):

    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), db.ForeignKey("users.username"))
    category_name = db.Column(db.String(100), unique=False)
    keywords = db.Column(db.String(300), unique=False)
    user = db.relationship("User", lazy="select", backref="categories")

    def __init__(self, username, category_name, keywords):
        self.username = username
        self.category_name = category_name
        self.keywords = keywords

    def __repr__(self):
        return "%s %s, %s>" % (self.username, self.category_name, self.keywords)


def stacked(df, categories):
    areas = dict()
    last = np.zeros(len(df[categories[0]]))
    for cat in categories:
        next = last + df[cat]
        areas[cat] = np.hstack((last[::-1], next))
        last = next
    return areas

def sql_to_pandas(sql_object):
    data_records = [rec.__dict__ for rec in sql_object]
    pandas_dframe = DataFrame.from_records(data_records)
    return pandas_dframe

def categorize_data(dframe, dframe_categories):
    dframe['Category'] = ''
    for ind in range(len(dframe_categories.index)):
        list_of_descriptions = list(dframe['Description'])
        list_of_keywords = dframe_categories.ix[ind, 'keywords'].split(',')
        item_indices = list()
        for keyword in list_of_keywords:
            item_indices.append([idx for idx, description in enumerate(list_of_descriptions) if search(keyword + '\s',
                                                                                                description) is not None])
        item_indices = sorted([item for sublist in item_indices for item in sublist], key=int)
        dframe.ix[item_indices, 'Category'] = dframe_categories.ix[ind, 'category_name']
    return dframe

def style_plot(plot):
    # Borders & Backgound
    plot.min_border_left = plot.min_border_right = 20
    plot.grid.minor_grid_line_color = '#eeeeee'
    plot.border_fill_color = "black"
    plot.background_fill_color = "beige"
    plot.background_fill_alpha = 0.6

    # Axes & Text
    plot.xaxis.axis_label_text_color = plot.yaxis.axis_label_text_color = "white"
    plot.xaxis.major_tick_line_color = plot.xaxis.minor_tick_line_color = \
        plot.yaxis.minor_tick_line_color = plot.yaxis.major_tick_line_color = "white"
    plot.title.text_color = plot.xaxis.major_label_text_color = plot.yaxis.major_label_text_color = "white"
    plot.xaxis.axis_line_color = plot.yaxis.axis_line_color = "white"

    # Legend
    plot.legend.background_fill_color = "gray" # "#e6e6e6"
    plot.legend.background_fill_alpha = 0.5
    plot.legend.label_text_font_style = "bold"