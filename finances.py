from flask import flash, render_template, request, redirect, url_for
from general import User, Categories, app, db, stacked, sql_to_pandas, categorize_data
from flask_login import LoginManager, login_required, login_user, logout_user
import pandas as pd
import numpy as np
from bokeh.plotting import figure
from bokeh.models import NumeralTickFormatter, DatetimeTickFormatter
from bokeh.embed import file_html, components
from bokeh.resources import CDN
from jinja2 import Environment
import io, csv, re


env = Environment(extensions=['jinja2.ext.autoescape'])
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    user = User(request.form["username"], request.form["password"])
    allUsers = [str(u) for u in User.query.all()]
    uname = request.form["username"]
    if uname not in allUsers:
        db.session.add(user)
        db.session.commit()
    else:
        flash("Username already exists! Choose another username or log into your account.")
    return redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    elif request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        registered_user = User.query.filter_by(username=username, password=password).first()
        if registered_user is None:
            registered_user2 = User.query.filter_by(username=username).first()
            if registered_user2 is None:
                flash("Username cannot be found. Please register.")
                return redirect(url_for("register"))
            else:
                flash("Incorrect password. Please try again.")
                return redirect(url_for("login"))
        login_user(registered_user)
        return redirect(url_for("dashboard", name=username))

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route("/dashboard/<name>", methods=["GET"])
@login_required
def dashboard(name):
    all_categories = Categories.query.filter_by(username=name)
    dframe_categories = sql_to_pandas(all_categories)
    dframe_categories = dframe_categories.ix[:, ['id', 'category_name', 'keywords']]
    colNames = ['category_name', 'keywords']
    return render_template("dashboard.html", name=name, colNames=colNames, dframe_categories=dframe_categories)

@app.route("/submit_category/<name>", methods=["POST"])
@login_required
def submit_category(name):
    category = Categories(name, request.form["category_name"], request.form["keywords"])
    db.session.add(category)
    db.session.commit()
    return redirect(url_for("dashboard", name=name))

@app.route("/delete_category/<int:id>", methods=["POST"])
@login_required
def delete_category(id):
    user = pd.DataFrame.from_records([rec.__dict__ for rec in Categories.query.filter_by(id=id).all()])
    username = user["username"].astype("str")[0]
    delcat = Categories.query.get(int(request.form["delete"]))
    db.session.delete(delcat)
    db.session.commit()
    return redirect(url_for("dashboard", name=username))

@app.route("/dashboard/<name>", methods=["POST"])
@login_required
def upload_data(name):
    f = request.files['csv_file']
    if not f:
        return 'No file'
    stream = io.StringIO(f.stream.read().decode('UTF8'), newline=None)
    csv_input = csv.reader(stream)
    data_list = [row for row in csv_input]
    columns = ['Date', 'Amount', 'Description']
    dframe = pd.DataFrame(data_list, columns=columns)
    dframe['Date'] = pd.to_datetime(dframe['Date'], format='%m/%d/%Y')
    dframe['Amount'] = dframe['Amount'].astype(float).fillna(0.0)

    dframe_categories = sql_to_pandas(Categories.query.filter_by(username=name))
    dframe_categories = dframe_categories.ix[:, ['id', 'category_name', 'keywords']]
    list_of_categories = dframe_categories['category_name'].tolist()
    dframe = categorize_data(dframe=dframe, dframe_categories=dframe_categories)
    dframe_grouped = dframe.groupby([pd.Grouper(freq='MS', key='Date'), 'Category']).sum().unstack().fillna(0.0) #.reset_index()
    final_df = dframe_grouped.xs('Amount', axis=1, drop_level=True).xs(list_of_categories, axis=1, drop_level=True)
    print(final_df)

    areas = stacked(final_df, list_of_categories)
    colors = list(areas.keys())
    for index, key in enumerate(colors):
        if key == "Groceries":
            colors[index] = 'green'
        elif key == "Amazon":
            colors[index] = 'yellow'
        elif key == 'Health':
            colors[index] = 'white'
        else:
            colors[index] = 'blue'

    print(final_df.index)

    date = np.hstack((final_df.index[::-1], final_df.index))
    print(date)
    print(areas)
    print(colors)

    TOOLS = "pan,box_zoom,undo,reset,save"
    expenditures_plot = figure(title="Expenditures", x_axis_type = 'datetime',
        tools=TOOLS, width=700, height=350, responsive=True, toolbar_location="above")
    expenditures_plot.grid.minor_grid_line_color = '#eeeeee'

    expenditures_plot.patches([date] * len(areas), [areas[cat] for cat in list_of_categories], color=colors, alpha=1,
        line_color=None)

    expenditures_plot.min_border_left = 20; expenditures_plot.min_border_right = 20
    expenditures_plot.xaxis.axis_label = "Date"
    expenditures_plot.yaxis.axis_label = "Amount"
    expenditures_plot.border_fill_color = "black"
    expenditures_plot.xaxis.axis_label_text_color = \
        expenditures_plot.yaxis.axis_label_text_color = "white"
    expenditures_plot.xaxis.major_tick_line_color = expenditures_plot.xaxis.minor_tick_line_color = \
        expenditures_plot.yaxis.minor_tick_line_color = expenditures_plot.yaxis.major_tick_line_color = "white"
    expenditures_plot.title.text_color = expenditures_plot.xaxis.major_label_text_color = \
        expenditures_plot.yaxis.major_label_text_color = "white"
    expenditures_plot.xaxis.axis_line_color = expenditures_plot.yaxis.axis_line_color = "white"

    for a, area in enumerate(areas):
        expenditures_plot.patch(date, areas[area], color=colors[a], legend=area, alpha=1, line_color=None)

    expenditures_plot.legend.background_fill_color = "#e6e6e6"
    expenditures_plot.legend.background_fill_alpha = 0.4
    expenditures_plot.legend.label_text_font_style = "bold"

    expenditures_plot.yaxis[0].formatter = NumeralTickFormatter(format="$0,0")
    expenditures_plot.xaxis.formatter = DatetimeTickFormatter(formats=dict(months=["%b %Y"], years=["%b %Y"])) #days=["%d %B %Y"],

    plots_created = True
    colNames = ['category_name', 'keywords']
    js_script, div = components(expenditures_plot)
    return render_template('dashboard.html', name=name, plots_created=plots_created, js_script=js_script,
                           colNames=colNames, dframe_categories=dframe_categories, div=div)


if __name__ == "__main__":
    db.create_all()
    app.run(debug=True)

'''
    ### PLOT

    dframe2 = dframe[:]
    dframe2['Grass Share'] = dframe2['grass_count'] / (
    dframe2['grass_count'] + dframe2['sheep_count'] + dframe2['wolf_count'])
    dframe2['Sheep Share'] = dframe2['sheep_count'] / (
    dframe2['grass_count'] + dframe2['sheep_count'] + dframe2['wolf_count'])
    dframe2['Wolf Share'] = dframe2['wolf_count'] / (
    dframe2['grass_count'] + dframe2['sheep_count'] + dframe2['wolf_count'])
    dframe2 = dframe2.ix[:, ['iter', 'Grass Share', 'Sheep Share', 'Wolf Share']]

    categories = ['Grass Share', 'Sheep Share', 'Wolf Share']
    areas = stacked(dframe2, categories)
    colors = list(areas.keys())
    for index, key in enumerate(colors):
      if key == "Grass Share":
        colors[index] = 'green'
      elif key == "Wolf Share":
        colors[index] = 'red'
      else:
        colors[index] = 'white'

    iter2 = np.hstack((dframe2['iter'][::-1], dframe2['iter']))

    TOOLS = "pan,box_zoom,undo,reset,save"
    expenditures_plot = figure(x_range=(1, len(dframe2['iter'])-1), y_range=(0, 1), title="Population Evolution (Shares)",
                            tools=TOOLS, width=700, height=350, responsive=True, toolbar_location="above")
    creature_plot2.grid.minor_grid_line_color = '#eeeeee'

    creature_plot2.patches([iter2] * len(areas), [areas[cat] for cat in categories], color=colors, alpha=1,
                           line_color=None)

    creature_plot2.min_border_left = 20; creature_plot2.min_border_right = 20
    creature_plot2.xaxis.axis_label = "Iteration"
    creature_plot2.yaxis.axis_label = "Share"
    creature_plot2.border_fill_color = "black"
    creature_plot2.xaxis.axis_label_text_color = \
      creature_plot2.yaxis.axis_label_text_color = "white"
    creature_plot2.xaxis.major_tick_line_color = creature_plot2.xaxis.minor_tick_line_color = \
      creature_plot2.yaxis.minor_tick_line_color = creature_plot2.yaxis.major_tick_line_color = "white"
    creature_plot2.title.text_color = creature_plot2.xaxis.major_label_text_color = \
      creature_plot2.yaxis.major_label_text_color = "white"
    creature_plot2.xaxis.axis_line_color = creature_plot2.yaxis.axis_line_color = "white"

    for a, area in enumerate(areas):
      creature_plot2.patch(iter2, areas[area], color=colors[a], legend=area, alpha=1, line_color=None)

    creature_plot2.legend.background_fill_color = "#e6e6e6"
    creature_plot2.legend.background_fill_alpha = 0.4
    creature_plot2.legend.label_text_font_style = "bold"

    creature_plot2.yaxis[0].formatter = NumeralTickFormatter(format="0%")

    html_text2 = file_html(creature_plot2, CDN, "Population Evolution")
    element_id2 = html_text2[
                 re.search("elementid", html_text2).start() + 12: re.search("elementid", html_text2).start() + 48]
    js_script2 = html_text2[re.search(r"function()", html_text2).start() - 8 : re.search("Bokeh.embed.embed_items",
                                                                                         html_text2).start() + 61]

'''
