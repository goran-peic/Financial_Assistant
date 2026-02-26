from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from pandas import DataFrame
from re import search
from flask_login import UserMixin
import numpy as np
import os


app = Flask(__name__)
database_url = os.environ.get("DATABASE_URL", "sqlite:///database.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SECRET_KEY"] = 'GiveMeABreak'
db = SQLAlchemy(app)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    password = db.Column(db.String(120), unique=False)

    def __init__(self, username, password):
        self.username = username
        self.password = password

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
    '''
    Prepares data for a stacked area chart by calculating cumulative sums.

    :param df: Pandas DataFrame containing the financial data.
    :param categories: List of category names to stack.
    :return: Dictionary of arrays representing the stacked areas.
    '''
    areas = dict()
    if not categories:
        return areas
    
    if df.empty:
        for cat in categories:
            areas[cat] = np.array([])
        return areas

    last = np.zeros(len(df.index))
    for cat in categories:
        next = last + df.get(cat, 0)
        areas[cat] = np.hstack((last[::-1], next))
        last = next
    return areas

def sql_to_pandas(sql_object):
    '''
    Converts a SQLAlchemy query result into a Pandas DataFrame.

    :param sql_object: SQLAlchemy query object or list of model instances.
    :return: Pandas DataFrame containing the records.
    '''
    data_records = [rec.__dict__ for rec in sql_object]
    pandas_dframe = DataFrame.from_records(data_records)
    return pandas_dframe

def categorize_data(dframe, dframe_categories):
    '''
    Categorizes transaction data based on user-defined categories and keywords.

    :param dframe: Pandas DataFrame containing transaction data with a 'Description' column.
    :param dframe_categories: Pandas DataFrame containing category names and associated keywords.
    :return: Updated DataFrame with a new 'Category' column.
    '''
    dframe['Category'] = ''
    for ind in range(len(dframe_categories.index)):
        list_of_descriptions = list(dframe['Description'])
        list_of_keywords = dframe_categories.iloc[ind]['keywords'].split(',')
        item_indices = list()
        for keyword in list_of_keywords:
            item_indices.append([idx for idx, description in enumerate(list_of_descriptions) if search(keyword + '\s',
                                                                                                description) is not None])
        item_indices = sorted([item for sublist in item_indices for item in sublist], key=int)
        dframe.loc[item_indices, 'Category'] = dframe_categories.iloc[ind]['category_name']
    return dframe

def style_plot(plot):
    '''
    Applies a consistent visual style to a Bokeh plot.

    :param plot: The Bokeh figure object to be styled.
    '''
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
    if hasattr(plot, 'legend'):
        legends = plot.legend
        if isinstance(legends, list) and len(legends) > 0:
            legend = legends[0]
            legend.background_fill_color = "gray" # "#e6e6e6"
            legend.background_fill_alpha = 0.1
            legend.label_text_font_style = "bold"
        elif hasattr(legends, 'background_fill_color'): # Old bokeh where legend is the object
            legends.background_fill_color = "gray"
            legends.background_fill_alpha = 0.1
            legends.label_text_font_style = "bold"