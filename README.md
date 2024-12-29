# A&M Jeans Inventory Management System

![A&M Logo](static/img/logo.png)

## 🚀 Overview
A powerful and modern inventory management system specifically designed for jeans retailers. Built with Flask and modern web technologies, offering a complete solution for managing inventory, sales, clients, and financial tracking.

## ✨ Key Features

### 📊 Dashboard
- Real-time inventory statistics
- Sales analytics
- Low stock alerts
- Recent transactions overview

### 🏭 Inventory Management
- Multi-warehouse support
- Barcode generation
- Stock tracking by size and color
- Automatic stock updates

### 💰 Sales & Invoicing
- Professional invoice generation
- Multiple payment methods
- Partial payment tracking
- Client debt management

### 👥 Client Management
- Detailed client profiles
- Purchase history
- Credit tracking
- Contact information

### 📈 Reports
- Sales reports
- Inventory valuation
- Client statements
- Financial summaries

## 🛠 Technical Stack
- **Backend**: Python/Flask
- **Database**: SQLite
- **Frontend**: TailwindCSS
- **Authentication**: Flask-Login
- **PDF Generation**: FPDF
- **Charts**: Chart.js

## 📸 Screenshots

### Dashboard
![Dashboard](screenshots/dashboard.png)

### Inventory
![Inventory](screenshots/inventory.png)

### Sales
![Sales](screenshots/sales.png)

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/hosenmekawy/A_M.git

# Navigate to project directory
cd A_M

# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Initialize database
flask db upgrade

# Run the application
flask run
```
