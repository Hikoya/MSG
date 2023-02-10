from flask import Flask
from flask import render_template
from flask import request
from flask import redirect, url_for
from flask import session, jsonify
	
from flask.ext.mysql import MySQL
from flask.ext.bcrypt import Bcrypt

import hashlib
import re

from datetime import datetime
from pytz import timezone

import pandas as pd

mysql = MySQL()

app = Flask(__name__)

# MySQL configurations
app.config['MYSQL_DATABASE_USER'] = 'cl'
app.config['MYSQL_DATABASE_PASSWORD'] = 'phyoekyawkyaw'
app.config['MYSQL_DATABASE_DB'] = 'acmicrogrid'
app.config['MYSQL_DATABASE_HOST'] = 'localhost'

mysql.init_app(app)
bcrypt = Bcrypt(app)

conn = mysql.connect()
cursor = conn.cursor()

table_name = "users"
table_prefix = "id_"
table_name_node = "nodes"
table_channels = "channels"

@app.route('/index')
def redirectIndex():
    return redirect(url_for('index'))

@app.route('/')
def index(name=None):
    if 'username' in session:
        node_result = get_all_node(session['username'])
        return render_template('index.html' , name= session['username'], node_result=node_result)
    return redirect(url_for('login'))

@app.route('/node', methods=['GET','POST'])
def node(name=None):
    if 'username' in session:
        if request.method == "POST": 
            if request.form.get('register') is not None:
                create_new_node(session['username'],request.form['deviceID'],request.form['description'],
                                request.form['location'])
            elif request.form.get('edit') is not None:
                edit_node(session['username'],request.form['deviceID_edit'],
                          request.form['description_edit'], request.form['location_edit'])
            elif request.form.get('delete') is not None:
                delete_node(session['username'],request.form['deviceID_edit'])            
        table = generate_node_table(session['username'])
        options = get_all_node_id(session['username'])
        return render_template('node.html' , name= session['username'], table = table, options = options)
    return redirect(url_for('login'))

@app.route('/profile' , methods=['GET', 'POST'])
def profile(name=None, write_key=""):
    if 'username' in session:
        if request.method == "POST":
            if update_key(session['username']):
                return redirect(url_for('profile'))
        write_key = get_key_from_db(session['username'])
        return render_template('profile.html' , name= session['username'] , write_key = write_key)
    return redirect(url_for('login'))

@app.route('/login' , methods=['GET','POST'])
def login():  
    if request.method == 'POST':
        if valid_login(request.form['username'],
                       request.form['password']):
            return log_the_user_in(request.form['username'])
    else:
        if 'username' in session:
            return redirect(url_for('index'))
        else:
            return render_template('login.html')
    
@app.route('/register' , methods=['GET','POST'])
def register():
    if 'username' in session:
        return redirect(url_for('index'))
    else:
        if request.method == 'POST':
            if(register_user(request.form['name'], request.form['username'], 
                          request.form['password'])):
                return redirect(url_for('index'))
            else:
                return render_template('register.html') 
        else:
            return render_template('register.html')
    
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/ajax', methods = ["POST"])
def ajax():
    if request.method == 'POST':
        deviceID = request.form.get('device_id')
        purpose = request.form.get('purpose')
        data = request.form.get('data')
        data_type = request.form.get('type')
        interval = request.form.get('interval')
        if does_node_exist(deviceID):
            if 'username' in session:
                username = session['username']
                if does_node_belong(deviceID,username):
                    if purpose == 'edit':
                        return populate_form(deviceID)
                    if purpose == 'average' and interval is not None:
                        return get_average(interval,deviceID)
                    if purpose == 'maxmin' and interval is not None:
                        return get_max_min(interval,deviceID)
                    if data is not None and data_type is None:
                        return get_latest_data(data, deviceID)
                    if data is not None and data_type is not None:
                        return get_all_data(data,data_type,deviceID)            				
    return ""

@app.route('/write_api', methods = ["GET","POST"])
def write_api():
    if request.method == "POST":
        data = request.form.get('data')
        #timestamp = request.form.get('timestamp')
        device_id = request.form.get('deviceID')
        return insert_data(data,device_id)
    else:
        return "FAIL"


@app.route('/predict', methods = ["GET","POST"])
def predict():
    if 'username' in session:        
        num_nodes = get_all_node(session['username'])
        table = []
        for node in num_nodes:
            num_channels = get_num_channels()
            for channel in num_channels:
                channel_query = "select voltage,current,frequency,power,energy from %s WHERE channel = %s " % (table_prefix + node['device_id'], channel)
                #timestamp_query = "select voltage,current,frequency,power,energy,timestamp from %s WHERE channel = %s " % (table_prefix + node['device_id'], channel)
                channel_data = pd.read_sql(channel_query, conn) 
                channel_table = channel_data.describe().to_html()
                
                #np.random.seed(1234)
                #data = pd.read_sql(timestamp_query, conn, index_col=['timestamp'] , parse_dates=['timestamp'])
        
                #ts = data["timestamp"]
                #print(ts.head(10))
                #model = ARIMA(data.as_matrix(), order=(5,1,0))
                #model_fit = model.fit(disp=0)
                #print(model_fit.summary())
             
                table.append(channel_table)
        return render_template('predict.html' , name= session['username'] , table = table)
    return redirect(url_for('login'))

        
app.secret_key = "b'\xba\x15\xe9\x12)\x8e7\xeb<\x1f\xbf\xedA\xe6tp\xf7\xc3\xbf>\x9f\x87]\xe8'"
    
if __name__ == "__main__":
    app.run()

def valid_login(username, password):
    check_qry = "Select username from %s where username='%s' " % (table_name, username)
    cursor.execute(check_qry)
    if cursor.rowcount > 0:
        password_qry = "select password from %s where username = '%s'" % (table_name, username)
        cursor.execute(password_qry)
        result_set = cursor.fetchone()
        for row in result_set:
            password_db = str(row)
        password_db = password_db.encode("utf-8")
        if bcrypt.check_password_hash(password_db, password):
            return True
        else:
            return False
    else:
        return False    
    return False

def log_the_user_in(username):
    session['username'] = username
    return redirect(url_for('index'))

def register_user(name, username, password): 
    cursor.execute("SELECT * FROM %s WHERE username = '%s' " % (table_name, username))
    if cursor.rowcount > 0:
        return False
    else:
        now = datetime.now()
        m = hashlib.md5()    
        key_data = username + str(now)
        key_data = key_data.encode('utf-8')
        m.update(key_data)
        write_key = m.hexdigest()
        write_key = write_key[:15]   
        hashed_password = bcrypt.generate_password_hash(password)
        hashed_password = hashed_password.decode("utf-8")
        insert_query = 'INSERT INTO %s (name,username,password,write_key) VALUES ("%s","%s","%s","%s")' % (table_name, name,username,hashed_password,write_key)
        #print(insert_query)
        cursor.execute(insert_query)
        conn.commit()
        if cursor.rowcount > 0:
            session['username'] = username
            return True
        else:
            return False 
    return False

def get_key_from_db(username):
    key_qry =  "SELECT write_key FROM %s WHERE username = '%s'" % (table_name, username)
    cursor.execute(key_qry)
    if cursor.rowcount > 0: 
        result_set = cursor.fetchone()
        for row in result_set:
            write_key = str(row)
        return write_key
    else:
        return ""

def update_key(username):
     now = datetime.now()
     m = hashlib.md5()    
     key_data = username + str(now)
     key_data = key_data.encode('utf-8')
     m.update(key_data)
     write_key = m.hexdigest()
     write_key = write_key[:15]   
     update_qry = "UPDATE %s SET write_key = '%s' WHERE username = '%s' " % (table_name, write_key, username)
     cursor.execute(update_qry)
     conn.commit()
     if cursor.rowcount > 0:
         return True
     else:
         return False
     
def generate_node_table(username):
    table_content = ""
    node_qry = "SELECT device_id,owner,description,location FROM %s WHERE owner = '%s'" % (table_name_node, username)
    cursor.execute(node_qry)
    if cursor.rowcount > 0 :
        result_set = cursor.fetchall()
        for row in result_set:
            #print(row)
            table_content += "<tr>"
            table_content += "<td>"+row[0]+"</td>"
            table_content += "<td>"+row[1]+"</td>"
            table_content += "<td>"+row[2]+"</td>"
            table_content += "<td>"+row[3]+"</td>"
            table_content += "</tr>"
    return table_content

def get_all_node_id(username):
    content = "<option value=''></option>";
    select_qry = "SELECT device_id FROM %s WHERE owner = '%s'" % (table_name_node, username)
    cursor.execute(select_qry)
    if cursor.rowcount > 0:
        result_set = cursor.fetchall()
        for row in result_set:
            content += "<option value='%s'>%s</option>" % (row[0], row[0])

    return content

def create_new_node(username,deviceID,description,location):
    select_qry = "SELECT id FROM %s WHERE device_id = '%s'" % (table_name_node, deviceID)
    cursor.execute(select_qry)
    if cursor.rowcount > 0 :
        return False
    else:
        insert_qry = "INSERT INTO %s (device_id,description,location,owner) VALUES ('%s','%s','%s','%s') " % (table_name_node, deviceID,description,location,username)
        cursor.execute(insert_qry)
        conn.commit()    
        table_qry = "CREATE TABLE %s (" % (table_prefix + deviceID) 
        table_qry += " id int(11) NOT NULL AUTO_INCREMENT," 
        table_qry += " device_id varchar(50) NOT NULL, " 
        table_qry += " channel int(11) NULL, " 
        table_qry += " voltage DOUBLE NULL, " 
        table_qry += " frequency DOUBLE NULL, " 
        table_qry += " current DOUBLE NULL, " 
        table_qry += " power DOUBLE NULL, " 
        table_qry += " energy DOUBLE NULL, " 
        table_qry += " timestamp DATETIME NOT NULL ," 
        table_qry += " PRIMARY KEY ( id )"
        table_qry += ")"
        cursor.execute(table_qry)
        conn.commit() 
        return True
    return False

def edit_node(username,deviceID,description,location):
    if(does_node_exist(deviceID)):
        if(does_node_belong(deviceID,username)):
            content = ""
            if description is not None and location is not None:
                content += "description = '%s' , " % (description)
                content += "location = '%s' " % (location)
            elif description is not None and location is None:
                content += "description = '%s' " % (description)
            elif description is None and location is not None:
                content += "location = '%s' " % (location)         
            if description is not None or location is not None:
                edit_query = "UPDATE %s SET " % (table_name_node)
                edit_query += content 
                edit_query += "WHERE device_id = '%s' " %(deviceID) 
                print(edit_query)
                cursor.execute(edit_query)
                conn.commit()
                return True
        else:
            return False
    else:
        return False

def delete_node(username,deviceID):
    if(does_node_exist(deviceID)):
        if(does_node_belong(deviceID,username)):
            table_qry = "DROP TABLE %s " % (table_prefix + deviceID)
            cursor.execute(table_qry)
            conn.commit()
            delete_qry = "DELETE FROM %s WHERE device_id = '%s' " % (table_name_node, deviceID)
            cursor.execute(delete_qry)
            conn.commit()
            return True
        else:
            return False
    else:
        return False
    return

def does_node_exist(deviceID):
    select_qry = "SELECT * FROM %s WHERE device_id = '%s' " % (table_name_node, deviceID)
    cursor.execute(select_qry)
    if cursor.rowcount > 0:
        return True
    else:
        return False;
		
def does_node_belong(deviceID, username):
    select_qry = "SELECT * FROM %s WHERE device_id = '%s' AND owner = '%s'" % (table_name_node, deviceID, username)
    cursor.execute(select_qry)
    if cursor.rowcount > 0:
        return True
    else:
        return False
    
def get_all_node(username):
    select_qry = "SELECT device_id, description,location FROM %s WHERE owner = '%s'" % (table_name_node, username)
    cursor.execute(select_qry)
    if cursor.rowcount > 0:
        result_set = cursor.fetchall()
        json_result = []
        for result in result_set:
            json_result_set = {
                    'device_id': result[0],
                    'description': result[1],
                    'location': result[2]
                    }
            json_result.append(json_result_set)
        return json_result
    else:
        return ""

def populate_form(deviceID):
    sql_query = "SELECT description,location FROM %s WHERE device_id = '%s' " % (table_name_node, deviceID)
    cursor.execute(sql_query)
    if cursor.rowcount > 0:
        results = cursor.fetchall()
        for row in results:
            description = row[0]
            location = row[1]       
            json_result = {
                'description': description,
                'location': location
            }
        return jsonify(json_result)
    else:
        return ""

def get_latest_data(data, deviceID):
    limit = 1
    tablename = table_prefix + deviceID
    channel_1 = "SELECT %s , timestamp FROM %s WHERE channel = '1' ORDER BY timestamp DESC LIMIT %i " % (data, tablename, limit)
    cursor.execute(channel_1)
    data_1_array = []
    time_array = []
    if cursor.rowcount > 0:	
        channel_1_results = cursor.fetchall()
        for result in channel_1_results:
            if result[0] is not None:
                data_1_array.append(float(result[0]))
                timestamp = result[1].strftime('%Y-%m-%d %H:%M:%S')
                time_array.append(timestamp)			
    channel_2 = "SELECT %s FROM %s WHERE channel = '2' ORDER BY timestamp DESC LIMIT %i" % (data, tablename, limit)
    cursor.execute(channel_2)
    data_2_array = []
    if cursor.rowcount > 0:
        channel_2_results = cursor.fetchall()
        for result in channel_2_results:
            if result[0] is not None:
                data_2_array.append(float(result[0]))					
    channel_3 = "SELECT %s FROM %s WHERE channel = '3' ORDER BY timestamp DESC LIMIT %i" % (data, tablename, limit) 
    cursor.execute(channel_3)
    data_3_array = []
    if cursor.rowcount > 0:
        channel_3_results = cursor.fetchall()
        for result in channel_3_results:
            if result[0] is not None:
                data_3_array.append(float(result[0]))  
    channel_4 = "SELECT %s FROM %s WHERE channel = '4' ORDER BY timestamp DESC LIMIT %i" % (data, tablename, limit) 
    cursor.execute(channel_4)
    data_4_array = []
    if cursor.rowcount > 0:
        channel_4_results = cursor.fetchall()
        for result in channel_4_results:
            if result[0] is not None:
                data_4_array.append(float(result[0]))
    channel_results = []
    channel_set = {
            "data" : data,
            "channel1" : data_1_array,
            "channel2" : data_2_array,
            "channel3" : data_3_array,
            "channel4" : data_4_array,
            "timestamp" : time_array
            }
    channel_results.append(channel_set)
    conn.commit()
    #print(channel_results)
    return jsonify(channel_set)

def get_all_data(data,data_type,deviceID):
    tablename = table_prefix + deviceID
    limit = int(data_type)
    channel_1 = "SELECT %s, timestamp FROM %s WHERE channel = '1' ORDER BY timestamp DESC LIMIT %i" % (data,tablename,limit)
    cursor.execute(channel_1)
    data_1_array = []
    time_array = []
    if cursor.rowcount > 0:
        channel_1_result = cursor.fetchall()
        for result in channel_1_result:
            if result[0] is not None:
                data_1_array.append(float(result[0]))
                timestamp = result[1].strftime('%Y-%m-%d %H:%M:%S')
                time_array.append(timestamp)			
    channel_2 = "SELECT %s FROM %s WHERE channel = '2' ORDER BY timestamp DESC LIMIT %i" % (data, tablename, limit)
    cursor.execute(channel_2)
    data_2_array = []
    if cursor.rowcount > 0:
        channel_2_results = cursor.fetchall()
        for result in channel_2_results:
            if result[0] is not None:
                data_2_array.append(float(result[0]))				
    channel_3 = "SELECT %s FROM %s WHERE channel = '3' ORDER BY timestamp DESC LIMIT %i" % (data, tablename, limit) 
    cursor.execute(channel_3)
    data_3_array = []
    if cursor.rowcount > 0:
        channel_3_results = cursor.fetchall()
        for result in channel_3_results:
            if result[0] is not None:
                data_3_array.append(float(result[0]))              
    channel_4 = "SELECT %s FROM %s WHERE channel = '4' ORDER BY timestamp DESC LIMIT %i" % (data, tablename, limit) 
    cursor.execute(channel_4)
    data_4_array = []
    if cursor.rowcount > 0:
        channel_4_results = cursor.fetchall()
        for result in channel_4_results:
            if result[0] is not None:
                data_4_array.append(float(result[0]))
    #channel_results = []
    if len(time_array) > 1:
        time_array.reverse()      
    channel_1 = []
    if len(data_1_array) > 1:
        data_1_array.reverse()
        for index, value in enumerate(data_1_array):
            channel_1.append([time_array[index], value])         
    channel_2 = []
    if len(data_2_array) > 1:
        data_2_array.reverse()
        for index, value in enumerate(data_2_array):
            channel_2.append([time_array[index],value])			
    channel_3 = []
    if len(data_3_array) > 1:
        data_3_array.reverse()
        for index, value in enumerate(data_3_array):
            channel_3.append([time_array[index],value])
    channel_4 = []
    if len(data_4_array) > 1:
        data_4_array.reverse()
        for index, value in enumerate(data_4_array):
            channel_4.append([time_array[index],value])		
    channel_set = {
            "data" : data,
            "channel1" : channel_1,
            "channel2" : channel_2,
            "channel3" : channel_3,
            "channel4" : channel_4
            }
    return jsonify(channel_set)

def get_average(interval,deviceID):
    tablename = table_prefix + deviceID
    timeInterval = ""
    if interval == "daily":
        timeInterval = "AND timestamp >= CURDATE()"
    elif interval == "monthly":
        timeInterval = "AND timestamp >= (NOW() - INTERVAL 1 MONTH)"
    elif interval == "yearly":
        timeInterval = "AND timestamp >= (NOW() - INTERVAL 1 YEAR)"
    elif interval == "weekly":
        timeInterval = "AND timestamp >= (NOW() - INTERVAL 1 WEEK)"
    else:
        timeInterval = "AND timestamp >= CURDATE()"				
    channel_1 = "SELECT AVG(voltage), AVG(frequency), AVG(current), AVG(power), AVG(energy) FROM %s WHERE channel = '1' %s " % (tablename, timeInterval)
    cursor.execute(channel_1)
    if cursor.rowcount > 0:
        channel_1_result = cursor.fetchall()
        for result in channel_1_result:
            if result[0] is not None:
                channel_1_voltage = result[0]
            else:
                channel_1_voltage = "Nil"
            if result[1] is not None:
                channel_1_frequency = result[1]
            else:
                channel_1_frequency = "Nil"
            if result[2] is not None:
                channel_1_current = result[2]
            else:
                channel_1_current = "Nil"
            if result[3] is not None:
                channel_1_power = result[3]
            else:
                channel_1_power = "Nil"
            if result[4] is not None:
                channel_1_energy = result[4]
            else:
                channel_1_energy = "Nil"
    else:
        channel_1_voltage = "Nil";
        channel_1_frequency = "Nil";
        channel_1_current = "Nil";
        channel_1_power = "Nil";
        channel_1_energy = "Nil";			
    channel_2 = "SELECT AVG(voltage), AVG(frequency), AVG(current), AVG(power), AVG(energy) FROM %s WHERE channel = '2' %s " % (tablename, timeInterval)
    cursor.execute(channel_2)
    if cursor.rowcount > 0:
        channel_2_result = cursor.fetchall()
        for result in channel_2_result:
            if result[0] is not None:
                channel_2_voltage = result[0]
            else:
                channel_2_voltage = "Nil"         
            if result[1] is not None:
                channel_2_frequency = result[1]
            else:
                channel_2_frequency = "Nil"        
            if result[2] is not None:
                channel_2_current = result[2]
            else:
                channel_2_current = "Nil"       
            if result[3] is not None:
                channel_2_power = result[3]
            else:
                channel_2_power = "Nil"         
            if result[4] is not None:
                channel_2_energy = result[4]
            else:
                channel_2_energy = "Nil"
    else:
        channel_2_voltage = "Nil";
        channel_2_frequency = "Nil";
        channel_2_current = "Nil";
        channel_2_power = "Nil";
        channel_2_energy = "Nil";								
    channel_3 = "SELECT AVG(voltage), AVG(frequency), AVG(current), AVG(power), AVG(energy) FROM %s WHERE channel = '3' %s " % (tablename, timeInterval)
    cursor.execute(channel_3)
    if cursor.rowcount > 0:
        channel_3_result = cursor.fetchall()
        for result in channel_3_result:
            if result[0] is not None:
                channel_3_voltage = result[0]
            else:
                channel_3_voltage = "Nil"              
            if result[1] is not None:
                channel_3_frequency = result[1]
            else:
                channel_3_frequency = "Nil"            
            if result[2] is not None:
                channel_3_current = result[2]
            else:
                channel_3_current = "Nil"     
            if result[3] is not None:
                channel_3_power = result[3]
            else:
                channel_3_power = "Nil"       
            if result[4] is not None:
                channel_3_energy = result[4]
            else:
                channel_3_energy = "Nil"
    else:
        channel_3_voltage = "Nil";
        channel_3_frequency = "Nil";
        channel_3_current = "Nil";
        channel_3_power = "Nil";
        channel_3_energy = "Nil";				
    channel_4 = "SELECT AVG(voltage), AVG(frequency), AVG(current), AVG(power), AVG(energy) FROM %s WHERE channel = '4' %s " % (tablename, timeInterval)
    cursor.execute(channel_4)
    if cursor.rowcount > 0:
        channel_4_result = cursor.fetchall()
        for result in channel_4_result:
            if result[0] is not None:
                channel_4_voltage = result[0]
            else:
                channel_4_voltage = "Nil"           
            if result[1] is not None:
                channel_4_frequency = result[1]
            else:
                channel_4_frequency = "Nil"        
            if result[2] is not None:
                channel_4_current = result[2]
            else:
                channel_4_current = "Nil"      
            if result[3] is not None:
                channel_4_power = result[3]
            else:
                channel_4_power = "Nil"
            if result[4] is not None:
                channel_4_energy = result[4]
            else:
                channel_4_energy = "Nil"
    else:
        channel_4_voltage = "Nil";
        channel_4_frequency = "Nil";
        channel_4_current = "Nil";
        channel_4_power = "Nil";
        channel_4_energy = "Nil";    
    channel_1 = {
            "voltage": channel_1_voltage,
            "frequency": channel_1_frequency,
            "current": channel_1_current,
            "power": channel_1_power,
            "energy": channel_1_energy
    }  
    channel_2 = {
            "voltage": channel_2_voltage,
            "frequency": channel_2_frequency,
            "current": channel_2_current,
            "power": channel_2_power,
            "energy": channel_2_energy
    }    
    channel_3 = {
            "voltage": channel_3_voltage,
            "frequency": channel_3_frequency,
            "current": channel_3_current,
            "power": channel_3_power,
            "energy": channel_3_energy
    }   
    channel_4 = {
            "voltage": channel_4_voltage,
            "frequency": channel_4_frequency,
            "current": channel_4_current,
            "power": channel_4_power,
            "energy": channel_4_energy
    }    
    channels = {
            "channel1": channel_1,
            "channel2": channel_2,
            "channel3": channel_3,
            "channel4": channel_4
    }    
    return jsonify(channels)

def insert_data(data,deviceID):
    if does_node_exist(deviceID):
        channels = re.split("\+", data)
        for channel in channels:
            if channel.find('Ch1') != -1:
                channel.replace('Ch1','')
                channel.replace(deviceID,'')
                channel_num = 1
                channel_data = re.findall('\d*\.\d*', channel)
                insert_into_db(deviceID,channel_data, channel_num)
            elif channel.find('Ch2') != -1:
                channel.replace('Ch2','')
                channel.replace(deviceID,'')
                channel_num = 2
                channel_data = re.findall('\d*\.\d*', channel)
                insert_into_db(deviceID,channel_data, channel_num)
            elif channel.find('Ch3') != -1:
                channel.replace('Ch3','')
                channel.replace(deviceID,'')
                channel_num = 3
                channel_data = re.findall('\d*\.\d*', channel)
                insert_into_db(deviceID,channel_data, channel_num)
            elif channel.find('Ch4') != -1:
                channel.replace('Ch4','')
                channel.replace(deviceID,'')
                channel_num = 4
                channel_data = re.findall('\d*\.\d*', channel)
                insert_into_db(deviceID,channel_data, channel_num)
        return "SUCCESS"
    return "FAIL"

def insert_into_db(deviceID,channel_data, channel_num):
    fmt = '%Y-%m-%d %H:%M:%S' 
    eastern = timezone('Asia/Singapore')  
    timenow = datetime.now(eastern) 
    timestamp = timenow.strftime(fmt)
    insert_qry = "INSERT into %s (device_id, channel, voltage, frequency, current, power, energy, timestamp) " % (table_prefix + deviceID)
    insert_qry += "VALUES ('%s' , '%s' , '%s' ," % (deviceID, channel_num, channel_data[0])
    insert_qry += "'%s', '%s', '%s', " % (channel_data[1],channel_data[2],channel_data[3])
    insert_qry += "'%s' , '%s') " % (channel_data[4], timestamp)
    cursor.execute(insert_qry)
    conn.commit()
    return "SUCCESS"

def get_max_min(interval, deviceID):
    tablename = table_prefix + deviceID
    timeInterval = ""
    if interval == "daily":
        timeInterval = "AND timestamp >= CURDATE()"
    elif interval == "monthly":
        timeInterval = "AND timestamp >= (NOW() - INTERVAL 1 MONTH)"
    elif interval == "yearly":
        timeInterval = "AND timestamp >= (NOW() - INTERVAL 1 YEAR)"
    elif interval == "weekly":
        timeInterval = "AND timestamp >= (NOW() - INTERVAL 1 WEEK)"
    else:
        timeInterval = "AND timestamp >= CURDATE()"				
    channel_1 = "SELECT MAX(voltage), MAX(frequency), MAX(current), MAX(power), MAX(energy), MIN(voltage), MIN(frequency), MIN(current), MIN(power), MIN(energy) FROM %s WHERE channel = '1' %s " % (tablename, timeInterval)
    cursor.execute(channel_1)
    if cursor.rowcount > 0:
        channel_1_result = cursor.fetchall()
        for result in channel_1_result:
            if result[0] is not None:
                channel_1_max_voltage = result[0]
            else:
                channel_1_max_voltage = "Nil"
            if result[1] is not None:
                channel_1_max_frequency = result[1]
            else:
                channel_1_max_frequency = "Nil"
            if result[2] is not None:
                channel_1_max_current = result[2]
            else:
                channel_1_max_current = "Nil"
            if result[3] is not None:
                channel_1_max_power = result[3]
            else:
                channel_1_max_power = "Nil"
            if result[4] is not None:
                channel_1_max_energy = result[4]
            else:
                channel_1_max_energy = "Nil"
            if result[5] is not None:
                channel_1_min_voltage = result[5]
            else:
                channel_1_min_voltage = "Nil"
            if result[6] is not None:
                channel_1_min_frequency = result[6]
            else:
                channel_1_min_frequency = "Nil"
            if result[7] is not None:
                channel_1_min_current = result[7]
            else:
                channel_1_min_current = "Nil"
            if result[8] is not None:
                channel_1_min_power = result[8]
            else:
                channel_1_min_power = "Nil"
            if result[9] is not None:
                channel_1_min_energy = result[9]
            else:
                channel_1_min_energy = "Nil"
    else:
        channel_1_max_voltage = "Nil";
        channel_1_max_frequency = "Nil";
        channel_1_max_current = "Nil";
        channel_1_max_power = "Nil";
        channel_1_max_energy = "Nil";
        channel_1_min_voltage = "Nil";
        channel_1_min_frequency = "Nil";
        channel_1_min_current = "Nil";
        channel_1_min_power = "Nil";
        channel_1_min_energy = "Nil";	
    channel_2 = "SELECT MAX(voltage), MAX(frequency), MAX(current), MAX(power), MAX(energy), MIN(voltage), MIN(frequency), MIN(current), MIN(power), MIN(energy) FROM %s WHERE channel = '2' %s " % (tablename, timeInterval)
    cursor.execute(channel_2)
    if cursor.rowcount > 0:
        channel_2_result = cursor.fetchall()
        for result in channel_2_result:
            if result[0] is not None:
                channel_2_max_voltage = result[0]
            else:
                channel_2_max_voltage = "Nil"         
            if result[1] is not None:
                channel_2_max_frequency = result[1]
            else:
                channel_2_max_frequency = "Nil"        
            if result[2] is not None:
                channel_2_max_current = result[2]
            else:
                channel_2_max_current = "Nil"       
            if result[3] is not None:
                channel_2_max_power = result[3]
            else:
                channel_2_max_power = "Nil"         
            if result[4] is not None:
                channel_2_max_energy = result[4]
            else:
                channel_2_max_energy = "Nil"
            if result[5] is not None:
                channel_2_min_voltage = result[5]
            else:
                channel_2_min_voltage = "Nil"
            if result[6] is not None:
                channel_2_min_frequency = result[6]
            else:
                channel_2_min_frequency = "Nil"
            if result[7] is not None:
                channel_2_min_current = result[7]
            else:
                channel_2_min_current = "Nil"
            if result[8] is not None:
                channel_2_min_power = result[8]
            else:
                channel_2_min_power = "Nil"
            if result[9] is not None:
                channel_2_min_energy = result[9]
            else:
                channel_2_min_energy = "Nil"
    else:
        channel_2_max_voltage = "Nil";
        channel_2_max_frequency = "Nil";
        channel_2_max_current = "Nil";
        channel_2_max_power = "Nil";
        channel_2_max_energy = "Nil";
        channel_2_min_voltage = "Nil";
        channel_2_min_frequency = "Nil";
        channel_2_min_current = "Nil";
        channel_2_min_power = "Nil";
        channel_2_min_energy = "Nil";									
    channel_3 = "SELECT MAX(voltage), MAX(frequency), MAX(current), MAX(power), MAX(energy), MIN(voltage), MIN(frequency), MIN(current), MIN(power), MIN(energy) FROM %s WHERE channel = '3' %s " % (tablename, timeInterval)
    cursor.execute(channel_3)
    if cursor.rowcount > 0:
        channel_3_result = cursor.fetchall()
        for result in channel_3_result:
            if result[0] is not None:
                channel_3_max_voltage = result[0]
            else:
                channel_3_max_voltage = "Nil"              
            if result[1] is not None:
                channel_3_max_frequency = result[1]
            else:
                channel_3_max_frequency = "Nil"            
            if result[2] is not None:
                channel_3_max_current = result[2]
            else:
                channel_3_max_current = "Nil"     
            if result[3] is not None:
                channel_3_max_power = result[3]
            else:
                channel_3_max_power = "Nil"       
            if result[4] is not None:
                channel_3_max_energy = result[4]
            else:
                channel_3_max_energy = "Nil"
            if result[5] is not None:
                channel_3_min_voltage = result[5]
            else:
                channel_3_min_voltage = "Nil"
            if result[6] is not None:
                channel_3_min_frequency = result[6]
            else:
                channel_3_min_frequency = "Nil"
            if result[7] is not None:
                channel_3_min_current = result[7]
            else:
                channel_3_min_current = "Nil"
            if result[8] is not None:
                channel_3_min_power = result[8]
            else:
                channel_3_min_power = "Nil"
            if result[9] is not None:
                channel_3_min_energy = result[9]
            else:
                channel_3_min_energy = "Nil"
    else:
        channel_3_max_voltage = "Nil";
        channel_3_max_frequency = "Nil";
        channel_3_max_current = "Nil";
        channel_3_max_power = "Nil";
        channel_3_max_energy = "Nil";
        channel_3_min_voltage = "Nil";
        channel_3_min_frequency = "Nil";
        channel_3_min_current = "Nil";
        channel_3_min_power = "Nil";
        channel_3_min_energy = "Nil";					
    channel_4 = "SELECT MAX(voltage), MAX(frequency), MAX(current), MAX(power), MAX(energy), MIN(voltage), MIN(frequency), MIN(current), MIN(power), MIN(energy) FROM %s WHERE channel = '4' %s " % (tablename, timeInterval)
    cursor.execute(channel_4)
    if cursor.rowcount > 0:
        channel_4_result = cursor.fetchall()
        for result in channel_4_result:
            if result[0] is not None:
                channel_4_max_voltage = result[0]
            else:
                channel_4_max_voltage = "Nil"           
            if result[1] is not None:
                channel_4_max_frequency = result[1]
            else:
                channel_4_max_frequency = "Nil"        
            if result[2] is not None:
                channel_4_max_current = result[2]
            else:
                channel_4_max_current = "Nil"      
            if result[3] is not None:
                channel_4_max_power = result[3]
            else:
                channel_4_max_power = "Nil"
            if result[4] is not None:
                channel_4_max_energy = result[4]
            else:
                channel_4_max_energy = "Nil"
            if result[5] is not None:
                channel_4_min_voltage = result[5]
            else:
                channel_4_min_voltage = "Nil"
            if result[6] is not None:
                channel_4_min_frequency = result[6]
            else:
                channel_4_min_frequency = "Nil"
            if result[7] is not None:
                channel_4_min_current = result[7]
            else:
                channel_4_min_current = "Nil"
            if result[8] is not None:
                channel_4_min_power = result[8]
            else:
                channel_4_min_power = "Nil"
            if result[9] is not None:
                channel_4_min_energy = result[9]
            else:
                channel_4_min_energy = "Nil"
    else:
        channel_4_max_voltage = "Nil";
        channel_4_max_frequency = "Nil";
        channel_4_max_current = "Nil";
        channel_4_max_power = "Nil";
        channel_4_max_energy = "Nil";  
        channel_4_min_voltage = "Nil";
        channel_4_min_frequency = "Nil";
        channel_4_min_current = "Nil";
        channel_4_min_power = "Nil";
        channel_4_min_energy = "Nil";	
    channel_1 = {
            "voltage": channel_1_max_voltage,
            "frequency": channel_1_max_frequency,
            "current": channel_1_max_current,
            "power": channel_1_max_power,
            "energy": channel_1_max_energy
    } 
    channel_1_min = {
            "voltage": channel_1_min_voltage,
            "frequency": channel_1_min_frequency,
            "current": channel_1_min_current,
            "power": channel_1_min_power,
            "energy": channel_1_min_energy
    }  
    channel_2 = {
            "voltage": channel_2_max_voltage,
            "frequency": channel_2_max_frequency,
            "current": channel_2_max_current,
            "power": channel_2_max_power,
            "energy": channel_2_max_energy
    }   
    channel_2_min = {
            "voltage": channel_2_min_voltage,
            "frequency": channel_2_min_frequency,
            "current": channel_2_min_current,
            "power": channel_2_min_power,
            "energy": channel_2_min_energy
    }  
    channel_3 = {
            "voltage": channel_3_max_voltage,
            "frequency": channel_3_max_frequency,
            "current": channel_3_max_current,
            "power": channel_3_max_power,
            "energy": channel_3_max_energy
    }
    channel_3_min = {
            "voltage": channel_3_min_voltage,
            "frequency": channel_3_min_frequency,
            "current": channel_3_min_current,
            "power": channel_3_min_power,
            "energy": channel_3_min_energy
    }  
    channel_4 = {
            "voltage": channel_4_max_voltage,
            "frequency": channel_4_max_frequency,
            "current": channel_4_max_current,
            "power": channel_4_max_power,
            "energy": channel_4_max_energy
    }
    channel_4_min = {
            "voltage": channel_4_min_voltage,
            "frequency": channel_4_min_frequency,
            "current": channel_4_min_current,
            "power": channel_4_min_power,
            "energy": channel_4_min_energy
    }      
    channels = {
            "channel1_max": channel_1,
            "channel2_max": channel_2,
            "channel3_max": channel_3,
            "channel4_max": channel_4,
            "channel1_min": channel_1_min,
            "channel2_min": channel_2_min,
            "channel3_min": channel_3_min,
            "channel4_min": channel_4_min
    }    
    return jsonify(channels)

def get_num_channels():
    channel_array = []
    channel_query = "SELECT channel_id FROM %s " % (table_channels)
    cursor.execute(channel_query)
    if cursor.rowcount > 0:
        channel_result = cursor.fetchall()
        for channel in channel_result:
            channel_array.append(channel[0])      
    return channel_array
