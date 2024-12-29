from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
import csv
import io
import os
from werkzeug.utils import secure_filename
from fpdf import FPDF

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['JSON_AS_ASCII'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Define base directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'inventory.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')

# Configure upload and backup directories
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
BACKUP_FOLDER = os.path.join(BASE_DIR, 'backups')
os.makedirs(BACKUP_DIR, exist_ok=True)

# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Update app config
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
from functools import wraps

if not os.path.exists('static/uploads'):
    os.makedirs('static/uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    role = db.Column(db.String(20), default='staff')  # 'owner', 'hr', 'staff'


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    location = db.Column(db.String(200))
    gender = db.Column(db.String(20))
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    invoices = db.relationship('Invoice', backref='client', lazy=True)

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'))    
    date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, default=0.0)
    paid_amount = db.Column(db.Float, default=0.0)
    remaining_amount = db.Column(db.Float, default=0.0)
    payments = db.relationship('Payment', backref='invoice', lazy=True)
    payment_method = db.Column(db.String(20))  # cash, visa, wallet
    payment_status = db.Column(db.String(20))  # paid, partial, pending
    status = db.Column(db.String(20), default='pending')  # pending, paid, cancelled
    items = db.relationship('InvoiceItem', backref='invoice', lazy=True)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'))
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
class Warehouse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200))
    description = db.Column(db.Text)
    items = db.relationship('InvoiceItem', back_populates='warehouse')

class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'))
    jeans_id = db.Column(db.Integer, db.ForeignKey('jeans.id'))
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'))  # Add this line
    quantity = db.Column(db.Integer)
    price = db.Column(db.Float)
    subtotal = db.Column(db.Float)
    jeans = db.relationship('Jeans', backref='invoice_items')
    warehouse = db.relationship('Warehouse', back_populates='items')


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You need admin privileges to access this page.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
@app.route('/register', methods=['GET', 'POST'])
@login_required
@admin_required
def register():
    if request.method == 'POST':
        username = request.form['username']
        
        # Check if user exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash(f'Username {username} is already taken. Please choose another username.')
            return redirect(url_for('register'))
            
        # Create new user if username is available
        new_user = User(
            username=username,
            password=request.form['password'],
            role=request.form['role'],
            is_admin=request.form['role'] in ['owner', 'hr']
        )
        db.session.add(new_user)
        db.session.commit()
        flash(f'User {username} created successfully!')
        return redirect(url_for('dashboard'))
    
    return render_template('register.html')

class JeansStock(db.Model):
    __tablename__ = 'jeans_stock'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    jeans_id = db.Column(db.Integer, db.ForeignKey('jeans.id'))
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'))
    quantity = db.Column(db.Integer, default=0)
    warehouse = db.relationship('Warehouse', backref='jeans_stocks')

class Jeans(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # اسم المنتج
    barcode = db.Column(db.String(50), unique=True)  # الكود
    sizes = db.Column(db.String(200), nullable=False)  # المقاسات
    colors = db.Column(db.String(200), nullable=False)  # الالوان
    price = db.Column(db.Float, nullable=False)  # السعر بالجنيه
    quantity = db.Column(db.Integer, default=0)
    pieces_per_dozen = db.Column(db.Integer, nullable=False)  # الدسته كام قطعه
    dozens_per_package = db.Column(db.Integer, nullable=False)  # الشيكاره كام دسته
    image_url = db.Column(db.String(200))
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    stocks = db.relationship('JeansStock', backref='jeans')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.barcode:
            self.barcode = f"JNS{datetime.now().strftime('%Y%m%d%H%M%S')}"

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    brand_name = db.Column(db.String(100), default='My Store')
    logo_url = db.Column(db.String(200))
    sidebar_image_url = db.Column(db.String(200))
    owner_email = db.Column(db.String(120))
    theme_color = db.Column(db.String(20), default='#007bff')
    about_title = db.Column(db.String(200))
    about_text = db.Column(db.Text)
    contact_phone = db.Column(db.String(50))
    contact_email = db.Column(db.String(120))
    show_dashboard = db.Column(db.Boolean, default=True)
    show_inventory = db.Column(db.Boolean, default=True)
    show_warehouses = db.Column(db.Boolean, default=True)
    show_sales = db.Column(db.Boolean, default=True)
    show_alerts = db.Column(db.Boolean, default=True)
    show_invoices = db.Column(db.Boolean, default=True)
    show_reports = db.Column(db.Boolean, default=True)
    show_debtors = db.Column(db.Boolean, default=True)
    show_clients = db.Column(db.Boolean, default=True)
    show_settings = db.Column(db.Boolean, default=True)
    sidebar_order = db.Column(db.String(500), default='dashboard,inventory,warehouses,sales,alerts,invoices,reports,debtors,clients')

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jeans_id = db.Column(db.Integer, db.ForeignKey('jeans.id'))
    quantity = db.Column(db.Integer, nullable=False)
    sale_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    jeans = db.relationship('Jeans', backref='sales')

with app.app_context():
    db.create_all()
    

@app.route('/')
def index():
    jeans = Jeans.query.all()
    return render_template('index.html', jeans=jeans)

@app.route('/create_invoice', methods=['GET', 'POST'])
@login_required
def create_invoice():
    if request.method == 'POST':
        invoice = Invoice(
            invoice_number=f'INV-{datetime.now().strftime("%Y%m%d%H%M%S")}',
            customer_name=request.form['customer_name'],
        )
        db.session.add(invoice)
        db.session.commit()
        return redirect(url_for('edit_invoice', invoice_id=invoice.id))
    return render_template('create_invoice.html')
@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        new_jeans = Jeans(
            name=request.form['name'],
            sizes=request.form['sizes'],
            colors=request.form['colors'],
            price=float(request.form['price']),
            pieces_per_dozen=int(request.form['pieces_per_dozen']),
            dozens_per_package=int(request.form['dozens_per_package'])
        )
        db.session.add(new_jeans)
        db.session.commit()

        # Add stock to selected warehouses
        warehouses = request.form.getlist('warehouses')
        quantities = request.form.getlist('quantities')
        
        for warehouse_id, quantity in zip(warehouses, quantities):
            if quantity and int(quantity) > 0:
                stock = JeansStock(
                    jeans_id=new_jeans.id,
                    warehouse_id=int(warehouse_id),
                    quantity=int(quantity)
                )
                db.session.add(stock)
        
        db.session.commit()
        flash('تم إضافة المنتج بنجاح', 'success')
        return redirect(url_for('inventory'))
        
    warehouses = Warehouse.query.all()
    return render_template('add.html', warehouses=warehouses)

@app.context_processor
def inject_settings():
    settings = Settings.query.first()
    if not settings:
        settings = Settings()
        db.session.add(settings)
        db.session.commit()
    return dict(settings=settings)


@app.route('/invoice/<int:invoice_id>/add_payment', methods=['POST'])
@login_required
def add_payment(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    amount = float(request.form['amount'])
    
    payment = Payment(
        invoice_id=invoice_id,
        amount=amount,
        payment_method=request.form['payment_method'],
        notes=request.form.get('notes', '')
    )
    
    invoice.paid_amount += amount
    invoice.remaining_amount = invoice.total_amount - invoice.paid_amount
    
    if invoice.remaining_amount <= 0:
        invoice.payment_status = 'paid'
        invoice.status = 'paid'
    elif invoice.paid_amount > 0:
        invoice.payment_status = 'partial'
        invoice.status = 'paid'
    else:
        invoice.status = 'pending'
        
    db.session.add(payment)
    db.session.commit()
    
    flash('تم تسجيل الدفع بنجاح', 'success')
    return redirect(url_for('edit_invoice', invoice_id=invoice_id))


@app.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    settings = Settings.query.first()
    if not settings:
        settings = Settings()
        db.session.add(settings)
        db.session.commit()
    
    if request.method == 'POST':
        
        settings.about_title = request.form.get('about_title')
        settings.about_text = request.form.get('about_text')
        settings.contact_phone = request.form.get('contact_phone')
        settings.contact_email = request.form.get('contact_email')
        settings.show_dashboard = 'show_dashboard' in request.form
        settings.show_inventory = 'show_inventory' in request.form
        settings.show_warehouses = 'show_warehouses' in request.form
        settings.show_sales = 'show_sales' in request.form
        settings.show_alerts = 'show_alerts' in request.form
        settings.show_invoices = 'show_invoices' in request.form
        settings.show_reports = 'show_reports' in request.form
        settings.show_debtors = 'show_debtors' in request.form
        settings.show_clients = 'show_clients' in request.form
        sidebar_items = request.form.getlist('sidebar_order')
        settings.show_settings = 'show_settings' in request.form
        new_order = request.form.getlist('sidebar_order')
        settings.sidebar_order = ','.join(sidebar_items)
        if new_order:
            settings.sidebar_order = ','.join(new_order)
        if 'logo' in request.files:
            logo = request.files['logo']
            if logo and allowed_file(logo.filename):
                filename = secure_filename(f"logo_{datetime.now().strftime('%Y%m%d%H%M%S')}.{logo.filename.rsplit('.', 1)[1]}")
                logo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                logo.save(logo_path)
                settings.logo_url = f"uploads/{filename}"

                
        
        if 'sidebar_image' in request.files:
            sidebar_image = request.files['sidebar_image']
            if sidebar_image and allowed_file(sidebar_image.filename):
                filename = secure_filename(f"sidebar_{datetime.now().strftime('%Y%m%d%H%M%S')}.{sidebar_image.filename.rsplit('.', 1)[1]}")
                sidebar_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                sidebar_image.save(sidebar_path)
                settings.sidebar_image_url = f"uploads/{filename}"
        
        # Update other settings
        settings.brand_name = request.form.get('brand_name')
        settings.owner_email = request.form.get('owner_email')
        settings.theme_color = request.form.get('theme_color')
        
        db.session.commit()
        flash('تم تحديث الإعدادات بنجاح', 'success')
        
    return render_template('settings.html', settings=settings)
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.username = request.form.get('username')
        if request.form.get('new_password'):
            current_user.password = request.form.get('new_password')
            email = request.form.get('email')
        if username and username != current_user.username:
            current_user.username = username
            
        if new_password:
            current_user.password = new_password
            
        if email:
            current_user.email = email
            
        db.session.commit()
        flash('Profile updated successfully!', 'success')
    return render_template('profile.html')

@app.route('/warehouses', methods=['GET'])
@login_required
def list_warehouses():
    warehouses = Warehouse.query.all()
    return render_template('warehouses/list.html', warehouses=warehouses)

@app.route('/warehouse/edit/<int:warehouse_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_warehouse(warehouse_id):
    warehouse = Warehouse.query.get_or_404(warehouse_id)
    if request.method == 'POST':
        warehouse.name = request.form['name']
        warehouse.location = request.form['location']
        warehouse.description = request.form['description']
        db.session.commit()
        flash('تم تحديث المخزن بنجاح', 'success')
        return redirect(url_for('list_warehouses'))
    return render_template('warehouses/edit.html', warehouse=warehouse)

@app.route('/warehouse/delete/<int:warehouse_id>', methods=['POST'])
@login_required
@admin_required
def delete_warehouse(warehouse_id):
    warehouse = Warehouse.query.get_or_404(warehouse_id)
    
    # Check if warehouse has any stock
    if warehouse.items:
        flash('لا يمكن حذف المخزن لأنه يحتوي على مخزون', 'danger')
        return redirect(url_for('list_warehouses'))
    
    db.session.delete(warehouse)
    db.session.commit()
    flash('تم حذف المخزن بنجاح', 'success')
    return redirect(url_for('list_warehouses'))

@app.route('/warehouse/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_warehouse():
    if request.method == 'POST':
        warehouse = Warehouse(
            name=request.form['name'],
            location=request.form['location'],
            description=request.form['description']
        )
        db.session.add(warehouse)
        db.session.commit()
        flash('Warehouse added successfully!')
        return redirect(url_for('list_warehouses'))
    return render_template('warehouses/add.html')



@app.route('/update/<int:id>', methods=['GET', 'POST'])
@login_required
def update(id):
    jeans = Jeans.query.get_or_404(id)
    if request.method == 'POST':
        try:
            jeans.barcode = request.form['barcode']
            jeans.name = request.form['name']
            jeans.sizes = request.form['sizes']
            jeans.colors = request.form['colors']
            jeans.price = float(request.form['price'])
            for stock in jeans.stocks:
                stock.quantity = int(request.form[f'quantity_{stock.warehouse_id}'])
            
            jeans.pieces_per_dozen = int(request.form['pieces_per_dozen'])
            jeans.dozens_per_package = int(request.form['dozens_per_package'])
            
            db.session.commit()
            flash('تم تحديث المنتج بنجاح', 'success')
            return redirect(url_for('inventory'))
        except:
            flash('حدث خطأ في تحديث المنتج', 'danger')
            
    return render_template('update.html', jeans=jeans)


@app.route('/delete/<int:id>')
def delete(id):
    jeans = Jeans.query.get_or_404(id)
    db.session.delete(jeans)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/export_csv')
@login_required
def export_csv():
    si = io.StringIO()
    si.write('\ufeff')  # Add BOM for Excel UTF-8 detection
    cw = csv.writer(si)
    cw.writerow(['المخزن', 'اسم المنتج', 'الكود', 'المقاسات', 'الألوان', 'السعر', 'الدسته', 'الشيكاره', 'الكمية'])
    
    inventory = db.session.query(Jeans, JeansStock, Warehouse)\
        .select_from(Jeans)\
        .join(JeansStock, Jeans.id == JeansStock.jeans_id)\
        .join(Warehouse, JeansStock.warehouse_id == Warehouse.id)\
        .all()
    
    for jeans, stock, warehouse in inventory:
        cw.writerow([
            warehouse.name,
            jeans.name,
            jeans.barcode,
            jeans.sizes,
            jeans.colors,
            jeans.price,
            jeans.pieces_per_dozen,
            jeans.dozens_per_package,
            stock.quantity
        ])
    
    output = si.getvalue()
    return send_file(
        io.BytesIO(output.encode('utf-8-sig')),  # Use utf-8-sig encoding
        mimetype='text/csv; charset=utf-8',
        as_attachment=True,
        download_name='inventory.csv'
    )

@app.route('/alerts')
@login_required
def alerts():
    low_stock = db.session.query(Jeans, JeansStock)\
        .join(JeansStock)\
        .filter(JeansStock.quantity < 48)\
        .all()
    return render_template('alerts.html', low_stock=low_stock)

@app.route('/sales')
@login_required
def sales():
    sales = db.session.query(
        Sale,
        Jeans
    ).join(Jeans).order_by(Sale.sale_date.desc()).all()
    return render_template('sales.html', sales=sales)

@app.route('/search')
@login_required
def search():
    query = request.args.get('q')
    results = Jeans.query.filter(
        (Jeans.brand.contains(query)) |
        (Jeans.style.contains(query)) |
        (Jeans.color.contains(query))
    ).all()
    return render_template('search_results.html', results=results)


@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password:  # Use proper password hashing in production
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template('login.html')

# Create initial user

import sqlite3
import shutil
from datetime import datetime

@app.route('/export_database')
@login_required
@admin_required
def export_database():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(BACKUP_FOLDER, f'backup_inventory_{timestamp}.db')
    
    # Create a copy of the database
    shutil.copy2(DB_PATH, backup_path)
    
    # Send the file
    return send_file(
        backup_path,
        as_attachment=True,
        download_name=f'inventory_backup_{timestamp}.db'
    )

@app.route('/import_database', methods=['POST'])
@login_required
@admin_required
def import_database():
    if 'database_file' not in request.files:
        flash('No database file uploaded', 'error')
        return redirect(url_for('settings'))
        
    file = request.files['database_file']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('settings'))
        
    if not file.filename.endswith('.db'):
        flash('Invalid database file', 'error')
        return redirect(url_for('settings'))
    
    # Save the uploaded file temporarily
    temp_path = os.path.join(BACKUP_DIR, 'temp_import.db')
    file.save(temp_path)
    
    try:
        # Verify it's a valid SQLite database
        conn = sqlite3.connect(temp_path)
        conn.close()
        
        # Replace the current database
        shutil.move(temp_path, DB_PATH)
        flash('Database imported successfully!', 'success')
    except Exception as e:
        flash(f'Invalid database file: {str(e)}', 'error')
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    return redirect(url_for('settings'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))



@app.route('/dashboard')
@login_required
def dashboard():
    total_items = db.session.query(db.func.sum(JeansStock.quantity)).scalar() or 0
    low_stock = db.session.query(JeansStock).filter(JeansStock.quantity < 48).count()
    paid_invoices = Invoice.query.filter_by(status='paid').count()
    partial_invoices = Invoice.query.filter_by(status='partial').count()
    pending_invoices = Invoice.query.filter_by(status='pending').count()
    recent_invoices = Invoice.query.order_by(Invoice.date.desc()).limit(5).all()
    total_sales = Sale.query.count()
    recent_sales = Sale.query.order_by(Sale.sale_date.desc()).limit(5).all()
    
    return render_template('dashboard.html', 
        total_items=total_items,
        low_stock=low_stock,
        total_sales=total_sales,
        recent_sales=recent_sales,
        paid_invoices=paid_invoices,
        partial_invoices=partial_invoices,
        pending_invoices=pending_invoices,
        recent_invoices=recent_invoices
    )

@app.route('/inventory')
@login_required
def inventory():
    items = Jeans.query.all()
    return render_template('inventory.html', items=items)

@app.route('/reports')
@login_required
def reports():
    today = datetime.now().date()
    dates = [(today - timedelta(days=x)) for x in range(6, -1, -1)]
    daily_sales = []
    
    for date in dates:
        daily_total = db.session.query(db.func.sum(Invoice.total_amount))\
            .filter(db.func.date(Invoice.date) == date)\
            .filter(Invoice.status == 'paid')\
            .scalar() or 0
        daily_sales.append(daily_total)
    
    arabic_days = ['السبت', 'الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة']
    labels = [arabic_days[date.weekday()] for date in dates]
    
    # Calculate total inventory value
    total_value = db.session.query(
        db.func.sum(Jeans.price * JeansStock.quantity)
    ).join(JeansStock).scalar() or 0
    
    # Calculate total sales from invoices
    total_sales_amount = db.session.query(db.func.sum(Invoice.total_amount))\
        .filter(Invoice.status == 'paid')\
        .scalar() or 0
        
    formatted_sales = "{:,.2f} جنيه مصري".format(total_sales_amount)
    
    payment_stats = db.session.query(
        Invoice.payment_method,
        db.func.sum(Invoice.paid_amount).label('total')
    ).group_by(Invoice.payment_method).all()
    
    pending_payments = db.session.query(
        Client,
        db.func.sum(Invoice.remaining_amount).label('total_pending')
    ).join(Invoice).filter(Invoice.payment_status != 'paid')\
     .group_by(Client.id).all()
    # Get top selling items from invoice items
    top_selling = db.session.query(
        Jeans,
        db.func.sum(InvoiceItem.quantity).label('total_sold')
    ).join(InvoiceItem)\
     .join(Invoice)\
     .filter(Invoice.status == 'paid')\
     .group_by(Jeans.id)\
     .order_by(db.desc('total_sold'))\
     .limit(5)\
     .all()
    
    return render_template('reports.html', 
        total_value=total_value,
        total_sales=formatted_sales,
        top_selling=top_selling,
        labels=labels,
        daily_sales=daily_sales,
        payment_stats=payment_stats,
        pending_payments=pending_payments
    )


@app.route('/debtors')
@login_required
def debtors():
    debtors = db.session.query(
        Client,
        db.func.sum(Invoice.remaining_amount).label('total_debt')
    ).join(Invoice)\
     .filter(Invoice.payment_status.in_(['pending', 'partial']))\
     .group_by(Client.id)\
     .having(db.func.sum(Invoice.remaining_amount) > 0)\
     .all()
    
    return render_template('debtors.html', debtors=debtors)


@app.route('/client/<int:client_id>/add_payment', methods=['POST'])
@login_required
def add_client_payment(client_id):
    client = Client.query.get_or_404(client_id)
    amount = float(request.form['amount'])
    payment_method = request.form['payment_method']
    notes = request.form.get('notes', '')

    # Get all unpaid invoices for this client
    unpaid_invoices = Invoice.query.filter_by(client_id=client_id)\
        .filter(Invoice.status.in_(['pending', 'partial']))\
        .order_by(Invoice.date).all()

    remaining_payment = amount
    for invoice in unpaid_invoices:
        if remaining_payment <= 0:
            break

        payment_for_invoice = min(remaining_payment, invoice.remaining_amount)
        
        payment = Payment(
            invoice_id=invoice.id,
            amount=payment_for_invoice,
            payment_method=payment_method,
            notes=f"دفع من {client.name}: {notes}"
        )
        
        invoice.paid_amount += payment_for_invoice
        invoice.remaining_amount = invoice.total_amount - invoice.paid_amount
        
        if invoice.remaining_amount <= 0:
            invoice.payment_status = 'paid'
        else:
            invoice.payment_status = 'partial'
            
        remaining_payment -= payment_for_invoice
        db.session.add(payment)
        
    db.session.commit()
    unpaid_count = Invoice.query.filter_by(client_id=client_id)\
        .filter(Invoice.status.in_(['pending', 'partial']))\
        .count()
        
    if unpaid_count == 0:
        flash(f'تم تسديد جميع مديونيات {client.name}', 'success')
    else:
        flash(f'تم تسجيل الدفع بنجاح. المتبقي: {remaining_payment:.2f} جنيه', 'success')
        
    return redirect(url_for('debtors'))


@app.route('/clients')
@login_required
def list_clients():
    clients = Client.query.all()
    return render_template('clients/list.html', clients=clients)

@app.route('/clients/export')
@login_required
def export_clients():
    si = io.StringIO()
    si.write('\ufeff')  # Add BOM for Excel UTF-8 detection
    cw = csv.writer(si)
    cw.writerow(['اسم العميل', 'رقم الهاتف', 'العنوان', 'عدد الفواتير', 'إجمالي المشتريات', 'المديونيات'])
    
    clients = Client.query.all()
    for client in clients:
        total_purchases = sum(invoice.total_amount for invoice in client.invoices)
        total_debt = sum(invoice.remaining_amount for invoice in client.invoices if invoice.status in ['pending', 'partial'])
        
        cw.writerow([
            client.name,
            client.phone,
            client.location,
            len(client.invoices),
            total_purchases,
            total_debt
        ])
    
    output = si.getvalue()
    return send_file(
        io.BytesIO(output.encode('utf-8-sig')),
        mimetype='text/csv; charset=utf-8',
        as_attachment=True,
        download_name='clients.csv'
    )

@app.route('/client/<int:client_id>')
@login_required
def view_client(client_id):
    client = Client.query.get_or_404(client_id)
    total_purchases = sum(invoice.total_amount for invoice in client.invoices)
    total_debt = sum(invoice.remaining_amount for invoice in client.invoices if invoice.status in ['pending', 'partial'])
    return render_template('clients/view.html', 
                         client=client, 
                         total_purchases=total_purchases,
                         total_debt=total_debt)

@app.route('/client/<int:client_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)
    if request.method == 'POST':
        client.name = request.form['name']
        client.phone = request.form['phone']
        client.location = request.form['location']
        client.gender = request.form['gender']
        db.session.commit()
        flash('تم تحديث بيانات العميل بنجاح', 'success')
        return redirect(url_for('list_clients'))
    return render_template('clients/edit.html', client=client)


@app.route('/warehouse/<int:warehouse_id>')
@login_required
def view_warehouse(warehouse_id):
    warehouse = Warehouse.query.get_or_404(warehouse_id)
    stocks = JeansStock.query.filter_by(warehouse_id=warehouse_id).all()
    return render_template('warehouses/view.html', warehouse=warehouse, stocks=stocks)

@app.route('/invoices')
@login_required
def list_invoices():
    invoices = Invoice.query.order_by(Invoice.date.desc()).all()
    return render_template('invoices/list.html', invoices=invoices)

@app.route('/invoice/create', methods=['GET', 'POST'])
@login_required
def new_invoice():
    if request.method == 'POST':
        client_id = request.form.get('client_id')
        
        if client_id:
            # Using existing client
            client = Client.query.get(client_id)
        else:
            # Creating new client
            client = Client(
                name=request.form.get('client_name', ''),
                phone=request.form.get('client_phone', ''),  # Changed from 'phone' to 'client_phone'
                location=request.form.get('client_location', ''),  # Changed from 'location' to 'client_location'
                gender=request.form.get('client_gender', 'male')  # Changed from 'gender' to 'client_gender'
            )
            db.session.add(client)
            db.session.commit()
            client_id = client.id

        invoice = Invoice(
            invoice_number=f'INV-{datetime.now().strftime("%Y%m%d%H%M%S")}',
            client_id=client_id,
            date=datetime.now()
        )
        db.session.add(invoice)
        db.session.commit()
        return redirect(url_for('edit_invoice', invoice_id=invoice.id))

    clients = Client.query.all()
    return render_template('invoices/create.html', clients=clients)

@app.route('/api/search_clients')
@login_required
def search_clients():
    query = request.args.get('q', '')
    clients = Client.query.filter(
        db.or_(
            Client.name.ilike(f'%{query}%'),
            Client.phone.ilike(f'%{query}%')
        )
    ).limit(5).all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'phone': c.phone,
        'location': c.location,
        'gender': c.gender
    } for c in clients])

@app.route('/api/create_client', methods=['POST'])
@login_required
def create_client():
    client = Client(
        name=request.form['client_name'],
        phone=request.form['client_phone'],
        location=request.form['client_location'],
        gender=request.form['client_gender']
    )
    db.session.add(client)
    db.session.commit()
    
    return jsonify({
        'id': client.id,
        'name': client.name,
        'phone': client.phone,
        'location': client.location,
        'gender': client.gender
    })
    
@app.route('/client/new', methods=['GET', 'POST'])
@login_required
def new_client():
    if request.method == 'POST':
        client = Client(
            name=request.form['name'],
            phone=request.form['phone'],
            location=request.form['location'],
            gender=request.form['gender']
        )
        db.session.add(client)
        db.session.commit()
        flash('تم إضافة العميل بنجاح', 'success')
        return redirect(url_for('new_invoice'))

    return render_template('clients/new.html')


@app.route('/invoice/<int:invoice_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    jeans = Jeans.query.all()
    warehouses = Warehouse.query.all()
    for item in invoice.items:
        item.product_name = item.jeans.name
    return render_template('invoices/edit.html', 
                         invoice=invoice, 
                         jeans=jeans,
                         warehouses=warehouses)


@app.route('/invoice/<int:invoice_id>/add_item', methods=['POST'])
@login_required
def add_invoice_item(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    jeans_id = request.form.get('jeans_id')
    warehouse_id = request.form.get('warehouse_id')
    quantity = int(request.form.get('quantity'))
    
    stock = JeansStock.query.filter_by(
        jeans_id=jeans_id,
        warehouse_id=warehouse_id
    ).first()
    
    if not stock or stock.quantity < quantity:
        flash(f'الكمية المتوفرة في المخزن: {stock.quantity if stock else 0}')
        return redirect(url_for('edit_invoice', invoice_id=invoice_id))
    
    jeans = Jeans.query.get(jeans_id)
    subtotal = jeans.price * quantity
    
    existing_item = InvoiceItem.query.filter_by(
        invoice_id=invoice_id,
        jeans_id=jeans_id,
        warehouse_id=warehouse_id
    ).first()
    
    if existing_item:
        existing_item.quantity += quantity
        existing_item.subtotal = existing_item.price * existing_item.quantity
        invoice.total_amount += subtotal
    else:
        item = InvoiceItem(
            invoice_id=invoice_id,
            jeans_id=jeans_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
            price=jeans.price,
            subtotal=subtotal
        )
        db.session.add(item)
        invoice.total_amount += subtotal
    
    stock.quantity -= quantity
    
    sale = Sale(
        jeans_id=jeans_id,
        quantity=quantity,
        total_amount=subtotal,
        sale_date=datetime.utcnow()
    )
    
    db.session.add(sale)
    db.session.commit()
    
    flash('تم إضافة المنتج بنجاح!')
    return redirect(url_for('edit_invoice', invoice_id=invoice_id))


class StyledPDF(FPDF):
    def header(self):
        self.set_font('Amiri', 'B', 16)
        self.set_text_color(0, 102, 204)
        self.cell(0, 10, self.title, ln=True, align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Amiri', 'I', 10)
        self.cell(0, 10, 'Page %s' % self.page_no(), align='C')
import arabic_reshaper
from bidi.algorithm import get_display
def create_sales_pdf(sales_data, title):
    pdf = StyledPDF()
    # Add all required fonts
    pdf.add_font('Amiri', '', 'static/fonts/Amiri-Regular.ttf', uni=True)
    pdf.add_font('Amiri', 'B', 'static/fonts/Amiri-Bold.ttf', uni=True)
    pdf.add_font('Amiri', 'I', 'static/fonts/Amiri-Italic.ttf', uni=True)
    pdf.add_font('Amiri', 'BI', 'static/fonts/Amiri-BoldItalic.ttf', uni=True)

    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.title = get_display(arabic_reshaper.reshape(title))  # Process title for Arabic
    pdf.add_page()

    # Table header
    pdf.set_font('Amiri', 'B', 12)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(60, 10, get_display(arabic_reshaper.reshape('التاريخ')), border=1, align='C', fill=True)
    pdf.cell(60, 10, get_display(arabic_reshaper.reshape('المبلغ')), border=1, align='C', fill=True)
    pdf.ln()

    # Table data
    pdf.set_font('Amiri', '', 12)
    row_fill = False
    total_amount = 0
    for date, amount in sales_data:
        total_amount += amount
        pdf.set_fill_color(245, 245, 245) if row_fill else pdf.set_fill_color(255, 255, 255)
        pdf.cell(60, 10, get_display(arabic_reshaper.reshape(date.strftime('%Y-%m-%d'))), border=1, align='C', fill=True)
        pdf.cell(60, 10, get_display(arabic_reshaper.reshape(f"{amount:,.2f} جنيه")), border=1, align='C', fill=True)
        pdf.ln()
        row_fill = not row_fill

    # Add total row
    pdf.set_font('Amiri', 'B', 12)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(60, 10, get_display(arabic_reshaper.reshape('الإجمالي')), border=1, align='C', fill=True)
    pdf.cell(60, 10, get_display(arabic_reshaper.reshape(f"{total_amount:,.2f} جنيه")), border=1, align='C', fill=True)
    pdf.ln()

    return pdf

@app.route('/download_sales_pdf/<period>')
@login_required
def download_sales_pdf(period):
    today = datetime.now()

    if period == 'day':
        start_date = today.date()
        title = f"مبيعات اليوم {start_date}"
        sales = Sale.query.filter(db.func.date(Sale.sale_date) == start_date).all()

    elif period == 'week':
        start_date = today.date() - timedelta(days=7)
        title = "مبيعات الأسبوع"
        sales = Sale.query.filter(Sale.sale_date >= start_date).all()

    elif period == 'month':
        start_date = today.replace(day=1)
        title = "مبيعات الشهر"
        sales = Sale.query.filter(Sale.sale_date >= start_date).all()

    else:  # total
        title = "إجمالي المبيعات"
        sales = Sale.query.all()

    sales_data = [(sale.sale_date, sale.total_amount) for sale in sales]
    pdf = create_sales_pdf(sales_data, title)

    # Write PDF to BytesIO without encoding issues
    pdf_output = io.BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)

    return send_file(
        pdf_output,
        download_name=f'sales_{period}.pdf',
        as_attachment=True,
        mimetype='application/pdf'
    )
    
@app.route('/invoice/<int:invoice_id>/delete', methods=['POST'])
@login_required
def delete_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Delete all invoice items first and restore stock
    for item in invoice.items:
        # Get the stock record for this item
        stock = JeansStock.query.filter_by(
            jeans_id=item.jeans_id,
            warehouse_id=item.warehouse_id
        ).first()
        
        if stock:
            # Restore the quantity to warehouse stock
            stock.quantity += item.quantity
            
        db.session.delete(item)
    
    # Delete any payments associated with this invoice
    Payment.query.filter_by(invoice_id=invoice_id).delete()
    
    # Delete the invoice
    db.session.delete(invoice)
    db.session.commit()
    
    flash('تم حذف الفاتورة بنجاح', 'success')
    return redirect(url_for('list_invoices'))

@app.route('/invoice/<int:invoice_id>/delete_item/<int:item_id>', methods=['POST'])
@login_required
def delete_invoice_item(invoice_id, item_id):
    item = InvoiceItem.query.get_or_404(item_id)
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Restore the quantity back to inventory
    jeans = Jeans.query.get(item.jeans_id)
    jeans.quantity += item.quantity
    
    # Update invoice total
    invoice.total_amount -= item.subtotal
    
    # Delete the sale record
    sale = Sale.query.filter_by(
        jeans_id=item.jeans_id,
        quantity=item.quantity,
        total_amount=item.subtotal
    ).first()
    
    if sale:
        db.session.delete(sale)
    
    # Delete the invoice item
    db.session.delete(item)
    db.session.commit()
    
    return redirect(url_for('edit_invoice', invoice_id=invoice_id))
@app.route('/invoice/<int:invoice_id>/print')
@login_required
def print_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template('invoices/print.html', invoice=invoice, timedelta=timedelta)

def initialize_database():
    with app.app_context():
        db.create_all()
        
        # Create initial admin if not exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                password='admin1234',
                is_admin=True,
                role='owner'
            )
            db.session.add(admin)
        
        # Create default settings if not exists
        settings = Settings.query.first()
        if not settings:
            settings = Settings(
                brand_name='My Store',
                theme_color='#007bff'
            )
            db.session.add(settings)
            
        # Create main warehouse if not exists
        main_warehouse = Warehouse.query.filter_by(name='Main Warehouse').first()
        if not main_warehouse:
            main_warehouse = Warehouse(
                name='Main Warehouse',
                location='Main Location',
                description='Primary warehouse location'
            )
            db.session.add(main_warehouse)
            
        db.session.commit()
if __name__ == '__main__':
    initialize_database()
    
    app.run(host='0.0.0.0', debug=True)
