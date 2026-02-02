from flask import flash, render_template, request, redirect, url_for
from general import User, Categories, app, db, stacked, sql_to_pandas, categorize_data, style_plot
from flask_login import LoginManager, login_required, login_user, logout_user
import pandas as pd
import numpy as np
from bokeh.palettes import inferno
from bokeh.plotting import figure
from bokeh.models import NumeralTickFormatter, DatetimeTickFormatter
from bokeh.embed import components
from bokeh.resources import CDN
import io, csv

app.config["SECRET_KEY"] = "ITSASECRET"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    user = User(request.form["username"], request.form["password"])
    all_users = [str(u) for u in User.query.all()]
    uname = request.form["username"]
    if uname not in all_users:
        db.session.add(user)
        db.session.commit()
    else:
        flash("Username already exists! Choose another username or log into your account.")
    return redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    else:
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

@app.route("/dashboard/<name>", methods=["GET", "POST"])
@login_required
def dashboard(name):
    # Common logic for GET and POST
    all_categories = Categories.query.filter_by(username=name)
    dframe_categories = sql_to_pandas(all_categories)
    
    if dframe_categories.empty:
        dframe_categories = pd.DataFrame(columns=['id', 'category_name', 'keywords'])
    else:
        dframe_categories = dframe_categories.loc[:, ['id', 'category_name', 'keywords']]
        
    col_names = ['category_name', 'keywords']

    if request.method == "GET":
        return render_template("dashboard.html", name=name, colNames=col_names, dframe_categories=dframe_categories, resources=CDN.render())

    elif request.method == "POST":
        # Load CSV File
        f = request.files.get('csv_file')
        if not f:
            flash('Please submit your raw data before requesting the report!')
            return redirect(url_for("dashboard", name=name))
        stream = io.StringIO(f.stream.read().decode('UTF8'), newline=None)
        csv_input = csv.reader(stream)
        data_list = [row for row in csv_input]
        columns = ['Date', 'Amount', 'Description']
        while True:
            try:
                dframe = pd.DataFrame(data_list, columns=columns)
                break
            except AssertionError:
                flash('Your CSV file is unreadable. Please check its format (columns, data, etc.).')
                return redirect(url_for("dashboard", name=name))
        dframe['Date'] = pd.to_datetime(dframe['Date'], format='%m/%d/%Y')
        dframe['Amount'] = dframe['Amount'].astype(float).fillna(0.0)

        # Import User Categories & Categorize Their Data
        dframe_categories_sql = sql_to_pandas(Categories.query.filter_by(username=name))
        if dframe_categories_sql.empty:
            flash('Please specify at least one category!')
            return redirect(url_for("dashboard", name=name))
        else:
            dframe_categories_sql = dframe_categories_sql.loc[:, ['id', 'category_name', 'keywords']]
            list_of_categories = dframe_categories_sql['category_name'].tolist()
            dframe = categorize_data(dframe=dframe, dframe_categories=dframe_categories_sql)
            dframe_grouped = dframe.groupby([pd.Grouper(freq='MS', key='Date'), 'Category']).sum().unstack().fillna(0.0) #.reset_index()
            
            final_df = dframe_grouped.xs('Amount', axis=1, drop_level=True)
            final_df = final_df.reindex(columns=list_of_categories, fill_value=0.0)
            
            final_df[list_of_categories] = final_df[list_of_categories].apply(lambda x: x * -1)
            print(final_df)

            # Create Plot
            tools = "pan,box_zoom,undo,reset,save"
            expenditures_plot = figure(title="Expenditures", x_axis_type = 'datetime', tools=tools, width=700, height=350,
                                       sizing_mode="scale_width", toolbar_location="above")

            spectral = inferno(len(list_of_categories))
            areas = stacked(final_df, list_of_categories)
            colors = list(areas.keys())
            for ind in range(len(list_of_categories)):
                colors[ind] = spectral[ind]

            date = np.hstack((final_df.index[::-1], final_df.index))
            expenditures_plot.patches([date] * len(areas), [areas[cat] for cat in list_of_categories], color=colors, alpha=1,
                                      line_color=None)

            # Style Plot
            expenditures_plot.xaxis.axis_label = "Date"
            expenditures_plot.yaxis.axis_label = "Amount"
            
            for a, area in enumerate(areas):
                expenditures_plot.patch(date, areas[area], color=colors[a], legend_label=area, alpha=1, line_color=None)
                
            style_plot(expenditures_plot)
            
            expenditures_plot.yaxis.formatter = NumeralTickFormatter(format="$0,0")
            expenditures_plot.xaxis.formatter = DatetimeTickFormatter(months="%b %Y", years="%b %Y") # days=["%d %B %Y"],
            
            if hasattr(expenditures_plot, 'legend') and len(expenditures_plot.legend) > 0:
                expenditures_plot.legend[0].orientation = "horizontal"
                expenditures_plot.legend[0].background_fill_alpha = 0.7

            js_script, div = components(expenditures_plot)
            plots_created = True

            return render_template('dashboard.html', name=name, plots_created=plots_created, js_script=js_script,
                                   colNames=['category_name', 'keywords'], dframe_categories=dframe_categories, div=div,
                                   resources=CDN.render())

@app.route("/submit_category/<name>", methods=["POST"])
@login_required
def submit_category(name):
    category = Categories(name, request.form["category_name"], request.form["keywords"])
    db.session.add(category)
    db.session.commit()
    return redirect(url_for("dashboard", name=name))

@app.route("/delete_category/<int:category_id>", methods=["POST"])
@login_required
def delete_category(category_id):
    delcat = db.session.get(Categories, category_id)
    if delcat:
        username = delcat.username
        db.session.delete(delcat)
        db.session.commit()
        return redirect(url_for("dashboard", name=username))
    return redirect(url_for("index"))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=False)
