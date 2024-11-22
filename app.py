#VoltWay - EV Charging Hub Finder
import os
import boto3
import random
import smtplib
from PIL import Image
from DBConnection import Db
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from evchargingfinderlib.booking import booking_success
from botocore.exceptions import NoCredentialsError
from flask import Flask, render_template, url_for, request, redirect, session, jsonify, flash

app = Flask(__name__)
app.secret_key="123"


def upload_file_to_s3(file_name, bucket_name, object_name=None):
    
    if object_name is None:
        object_name = file_name.split("/")[-1]

    # Initialize S3 client
    s3_client = boto3.client('s3')
    try:
        # Upload the file
        s3_client.upload_file(file_name, bucket_name, object_name)
        print(f"File '{file_name}' uploaded successfully to '{bucket_name}/{object_name}'")
        return True
    except FileNotFoundError:
        print("Error: The file was not found.")
    except NoCredentialsError:
        print("Error: AWS credentials not available.")
    except Exception as e:
        print(f"Error: {e}")
    return False


#//////////////////////////////////////////////////////////////COMMON/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


@app.route('/')
def home():
    session.pop('username',None)
    session.pop('user_type',None)
    session.pop('log',None)
    session.pop('usertype',None)
    return render_template('index.html')


@app.route('/find_your_charger')
def find_your_charger():
    if  'user_type' in session and session['user_type'] != "admin":
        return render_template('find_your_charger.html')
    else:
        return render_template('login.html')


@app.route('/contact_us', methods=['GET', 'POST'])
def contact_us():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        feedback = request.form['message']
        db = Db()
        sql = db.insert("INSERT INTO contact_us (Name, Email, feedback_date, feedback) VALUES (%s, %s, NOW(), %s)", (name, email, feedback))
        return render_template('contact_us.html', message='Thank you for your feedback!')
    else:
        return render_template('contact_us.html')



@app.route('/login',methods=['GET', 'POST'])
def login():
    if  'user_type' in session and session['user_type'] == "admin":
        return redirect('/admin-home')

    if request.method == "POST":
        print('form ', request.form)
        username = request.form['username']
        password = request.form['password']
        db = Db()
        ss = db.selectOne("select * from login where username='" + username + "'and password='" + password + "'")
        if ss is not None:
            session['head'] = ""
            session['username'] = username # set the username key in the session
            if ss['usertype'] == 'admin':
                session['user_type'] = 'admin'
                return redirect('/admin-home')

            elif ss['usertype'] == 'user':
                session['user_type'] = 'user'
                session['uid'] = ss['login_id']
                return redirect('/user-dashboard')
            else:
                return '''<script>alert('user not found');window.location="/login"</script>'''
        else:
            return '''<script>alert('user not found');window.location="/login"</script>'''
    return render_template("login.html")


@app.route('/logout')
def logout():
    session.pop('username',None)
    session.pop('user_type',None)
    session.pop('log',None)
    session.pop('usertype',None)

    return redirect('/login')



    # =========================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "POST":
        username = request.form['signupUsername']
        email = request.form['email']
        password = request.form['password']
        confirmPassword = request.form['confirmPassword']

        # Perform form validation
        if username.strip() == '':
            return redirect(url_for('register', error='Please enter a username', form_id='createAccount'))

        if email.strip() == '':
            return redirect(url_for('register', error='Please enter an email address', form_id='createAccount'))

        if password.strip() == '':
            return redirect(url_for('register', error='Please enter a password', form_id='createAccount'))

        if confirmPassword.strip() == '':
            return redirect(url_for('register', error='Please confirm the password', form_id='createAccount'))

        if password != confirmPassword:
            return redirect(url_for('register', error='Passwords do not match', form_id='createAccount'))

        db = Db()
        qry = db.insert("INSERT INTO login (username, email, password, usertype) VALUES (%s, %s, %s, 'user')", (username,  email, password))

        return '<script>alert("User registered"); window.location.href="/login";</script>'
    else:
        error = request.args.get('error')  # Get the error message from the URL parameters
        return render_template("login.html", error=error , form_id='createAccount')






#////////////////////////////////////////////////////////////ADMIN///////////////////////////////////////////////////////////////////////////////////////////////////////////////////


@app.route('/admin-home')
def admin_home():
    if 'user_type' not in session:
        return redirect('/')
    else:
        if session['user_type'] == 'admin':
            username = session['username'] # get the username from the session
            return render_template('admin/admin-login-dashboard.html', username=username)
        else:
            return redirect('/')


@app.route('/Manage_station')
def Manage_station():
    if 'user_type' not in session:
        return redirect('/')
    else:
        if session['user_type'] == 'admin':
            username = session['username']
            db=Db()
            qry=db.select("select station_id, station_name, address, city, charger_type, available_ports, status from admin_charging_station_list")
            return render_template("admin/Manage_station.html",data=qry,username=username)
        else:
            return redirect('/')


@app.route('/addstationpage')
def addstationpage():
    if 'user_type' not in session:
        return redirect('/')
    else:
        if session['user_type'] == 'admin':
            username = session['username'] # get the username from the session
            return render_template('admin/add_station.html', username=username)
        else:
            return redirect('/')


#image exe
ALLOWED_EXTENSIONS = {'jpg'}
def allowed_file(filename):
  return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



@app.route('/addchargingstation', methods=['POST'])
def addchargingstation():
    if 'user_type' not in session:
        return redirect('/')
    else:
        if session['user_type'] == 'admin':
            username = session['username']
            savepath = './static/image/'
            file = None
            file = request.files['file']
            if file and allowed_file(file.filename):
                stationname = request.form['stationname']
                address = request.form['address']
                city = request.form['city']
                chargetype = request.form['chargetype']
                ports = str(request.form['ports'])
                image = Image.open(file)
                imagepath = os.path.join(savepath,file.filename)
                image.save(imagepath)
                file_name = imagepath 
                bucket_name = "evlocator"      
                upload_file_to_s3(file_name, bucket_name)

            status = 'active'
            db = Db()
            qry = db.insert("INSERT INTO admin_charging_station_list VALUES (NULL, %s, %s, %s, %s, %s, %s, %s)", (stationname,address,city,chargetype,ports,imagepath,status))

            return render_template('admin/add_station.html', username=username, successmsg="Charging Station Added Successfully !!!")


        else:
            return redirect('/')



# =============================contact_us
@app.route('/view_feedback')
def view_feedback():
    if 'user_type' not in session:
        return redirect('/')
    else:
        #print('session ', session)
        if session['user_type'] == 'admin':
            username = session['username']
            db=Db()
            ss=db.select("select * from contact_us")
            return render_template("admin/view_feedback.html",data=ss, username=username)
        else:
            return redirect('/')

# 


# ==================delete station=======
@app.route("/adm_delete_station/<station_name>")
def adm_delete_station(station_name):
    if 'user_type' not in session:
        return redirect('/')
    else:
        #print('session ', session)
        if session['user_type'] == 'admin':
            username = session['username']
            db = Db()
            qry = db.delete("DELETE FROM admin_charging_station_list WHERE Station_name = %s", (station_name,))
            return '''<script>alert('station deleted');window.location="/Manage_station"</script>'''
        else:
            return redirect('/')
# =======================================





@app.route("/adm_delete_feedback/<feedback>")
def adm_delete_feedback(feedback):
    if 'user_type' not in session:
        return redirect('/')
    else:
        #print('session ', session)
        if session['user_type'] == 'admin':
            username = session['username']
            db = Db()
            qry = db.delete("delete from contact_us where Sl_no='"+feedback+"'")
            return '''<script>alert('feedback deleted');window.location="/view_feedback"</script>'''
        else:
            return redirect('/')



@app.route('/user-list')
def user_list():
    if 'user_type' not in session:
        return redirect('/')
    else:
        if session['user_type'] == 'admin':
            username = session['username']
            db=Db()
            qry = db.select("SELECT * FROM `login` WHERE usertype='user'")
            return render_template("admin/user-list.html",data=qry,username=username)
        else:
            return redirect('/')


# ==================delete user===========
@app.route("/adm_delete_user/<login_id>")
def adm_delete_user(login_id):
    if 'user_type' not in session:
        return redirect('/')
    else:
        #print('session ', session)
        if session['user_type'] == 'admin':
            username = session['username']
            db = Db()
            qry = db.delete("delete from login   where login_id='"+login_id+"'")
            return '''<script>alert('user deleted');window.location="/user-list"</script>'''
        else:
            return redirect('/')
# ==============view booking=========================

@app.route('/view_booking')
def view_booking():
    if 'user_type' not in session:
        return redirect('/')
    else:
        #print('session ', session)
        if session['user_type'] == 'admin':
            username = session['username']
            db=Db()
            bookings = db.select("select Booking_id	, Booking_date, Time_from, Time_to, City, Station_name, Available_ports, login_id  from booking  order by Booking_date desc;")
            return render_template('admin/view_booking.html', bookings=bookings,username=username)
        else:
            return redirect('/')

# ===========delete booking

@app.route("/adm_delete_booking/<Booking_id>")
def adm_delete_booking(Booking_id):
    if 'user_type' not in session:
        return redirect('/')
    else:
        #print('session ', session)
        if session['user_type'] == 'admin':
            db = Db()
            qry = db.delete("delete from booking where Booking_id='"+Booking_id+"'")
            return '''<script>alert('booking deleted');window.location="/view_booking"</script>'''
        else:
            return redirect('/')



#//////////////////////////////////////////////////////////////USER//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

# -----------

@app.route('/user-dashboard')
def user_dashboard():
    if 'user_type' in session and session['user_type'] == "user":
        username = session['username'] # get the username from the session
        db = Db()
        bookings = db.select("select * from booking where login_id = '%s' order by Booking_date desc;", (session['uid'],))
        # print(bookings)  # print out the value of the bookings variable
        return render_template("user/user-login-dashboard.html", bookings=bookings, username=username)
    else:
        return redirect('/')


@app.route('/usr_delete_booking/<int:booking_id>')
def usr_delete_booking(booking_id):
    if 'user_type' in session and session['user_type'] == "user":
        username = session['username']
        if 'user_type' in session and session['user_type'] == "user":
            db = Db()
            
            # Delete the booking for the specific user and booking_id
            db.delete("DELETE FROM booking WHERE booking_id = %s AND login_id = %s", (booking_id, session['uid']))
            
            return '''<script>alert('Booking deleted');window.location="/user-dashboard"</script>'''
        else:
            return redirect('/user-dashboard')
    
    else:
        return redirect('/')



@app.route('/user_find_your_charger', methods=['GET', 'POST'])
def user_find_your_charger():
    if 'user_type' in session and session['user_type'] == 'user':
        username = session['username']
        if request.method == 'POST':
            city = request.form.get('City')
            charger_type = request.form.get('Charger_type')
            db = Db()
            qry = db.select("select Station_name, Address, Charger_type, Available_ports from admin_charging_station_list where City = %s and Charger_type = %s", (city, charger_type))
            return render_template('user/station_search.html', data=qry, username=username)       
        else:
            return render_template('user/user_find_your_charger.html', username=username)
    else:
        return redirect('/')




@app.route('/search_stations', methods=['POST'])
def search_stations():
    if 'user_type' in session and session['user_type'] == 'user':
        username = session['username']
        # Get the form data
        City = request.form.get('City')
        Charger_type = request.form.get('Charger_type')

        # Redirect to the station_list page with the city and charger_type as URL parameters
        return redirect(url_for('station_search', City=City, Charger_type=Charger_type, username=username))
    else:
        return redirect('/')


@app.route('/station_search', methods=['GET'])
def station_search():
    if 'user_type' in session and session['user_type'] == 'user':
        username = session['username']
        City = request.args.get('City')
        Charger_type = request.args.get('Charger_type')
        # Query your MySQL database using the city and charge_type variables
        db = Db()
        sql = "select * from admin_charging_station_list where City = %s and Charger_type = %s"
        ss = db.select(sql, (City, Charger_type))

        # Return the results to the user in a new template
        return render_template('user/station_search.html', data=ss, City=City, Charger_type=Charger_type, username=username)
    else:
        return redirect('/')

# ==============from station_search to booking page====================
@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if 'user_type' in session and session['user_type'] == 'user':
        username = session['username']
        if request.method == 'POST':
            Station_name = request.form['Station_name']
            City = request.form['City']
            Available_ports = request.form['Available_ports']
            db = Db()
            sql = "select filepath from admin_charging_station_list where Station_name = %s"
            ss = db.select(sql, (Station_name,))
            #print(ss[0]['filepath'])
            imgfilename = str(ss[0]['filepath'])
            imgfilename = imgfilename.split('/')[-1]
            imgfilename = 'https://evlocator.s3.us-east-1.amazonaws.com/'+imgfilename
            #print(imgfilename)
            return redirect(url_for('booking_form',  Station_name=Station_name, City=City, Available_ports=Available_ports, outputimgpath=imgfilename))
        else:
            # handle GET request to display the form
            Station_name = request.args.get('Station_name')
            City = request.args.get('City')
            Available_ports = request.args.get('Available_ports')
            db = Db()
            sql = "select filepath from admin_charging_station_list where Station_name = %s"
            ss = db.select(sql, (Station_name,))
            imgfilename = str(ss[0]['filepath'])
            imgfilename = imgfilename.split('/')[-1]
            imgfilename = 'https://evlocator.s3.us-east-1.amazonaws.com/'+imgfilename
            return redirect(url_for('booking_form', Station_name=Station_name, City=City, Available_ports=Available_ports, username=username, outputimgpath=imgfilename))
    else:
        return redirect('/')


@app.route('/booking-form', methods=['GET'])
def booking_form():
    if 'user_type' in session and session['user_type'] == 'user':
        username = session['username']
        city = request.args.get('City')
        available_ports = request.args.get('Available_ports')
        station_name = request.args.get('Station_name')
        db = Db()
        station_data = db.select("select * from admin_charging_station_list where Station_name = %s", (station_name,))
        db = Db()
        sql = "select filepath from admin_charging_station_list where Station_name = %s"
        ss = db.select(sql, (station_name,))
        imgfilename = str(ss[0]['filepath'])
        imgfilename = imgfilename.split('/')[-1]
        imgfilename = 'https://evlocator.s3.us-east-1.amazonaws.com/'+imgfilename
        session['station_data'] = station_data[0] if station_data else None
        if 'station_data' in session and session['station_data']:
            
            return render_template('/user/booking_form.html', city=city, available_ports=available_ports, username=username, outputimgpath=imgfilename)
        else:
            return redirect(url_for('station_search'))
    else:
        return redirect('/')


# ====================from booking to dashboard

@app.route('/book', methods=['POST'])
def book():
    if 'user_type' not in session and session['user_type'] != 'user':
        return redirect('/')
    
    else:
        username = session['username']
        # get the form data submitted by the user
        station_name = request.form['Station_name']
        city = request.form['City']
        available_ports = request.form['Available_ports']
        booking_date = request.form['Booking_date']
        time_from = request.form['Time_from']
        time_to = request.form['Time_to']
        login_id = session['uid']


        db = Db()

        # get the current timestamp
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # insert the booking data into the MySQL table
        sql = "insert into booking (Station_name, City, Available_ports, Booking_date, Time_from, Time_to, Created_id, login_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        booking_id = db.insert(sql, (station_name, city, available_ports, booking_date, time_from, time_to, created_at, login_id))
        booksuccessmsg = booking_success()
        #Send SNS notification
        topicOfArn = 'arn:aws:sns:us-east-1:730335467273:evbooking01'
        subjectToSend = 'Booking'
        messageToSend = f'Booking Successfully'
        AWS_REGION = 'us-east-1'
        sns_client = boto3.client('sns', region_name=AWS_REGION)
        response = sns_client.publish(
            TopicArn=topicOfArn,
            Message=messageToSend,
            Subject=subjectToSend,
        )
        print(response)
        # redirect the user to their dashboard
        return render_template('/user/booking_form.html', booksuccessmsg=booksuccessmsg)




if __name__ == '__main__':        
    app.run(host='127.0.0.1', port=5000, debug=False)




