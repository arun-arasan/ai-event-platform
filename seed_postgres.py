import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def init_postgres():
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "enterprise_db"),
        user=os.getenv("POSTGRES_USER", "devuser"),
        password=os.getenv("POSTGRES_PASSWORD", "devpassword")
    )
    cursor = conn.cursor()

    # Create schema
    cursor.execute("""
    DROP TABLE IF EXISTS orders;
    DROP TABLE IF EXISTS customers;

    CREATE TABLE customers (
        customer_id VARCHAR(50) PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        email VARCHAR(100) NOT NULL,
        tier VARCHAR(20) DEFAULT 'Standard'
    );

    CREATE TABLE orders (
        order_id VARCHAR(50) PRIMARY KEY,
        customer_id VARCHAR(50) REFERENCES customers(customer_id),
        product_name VARCHAR(100) NOT NULL,
        status VARCHAR(50) NOT NULL,
        delivery_date DATE,
        amount_usd NUMERIC(10, 2) NOT NULL
    );
    """)

    # Seed initial test data
    cursor.execute("""
    INSERT INTO customers (customer_id, name, email, tier) VALUES
        ('CUST-101', 'Alice Johnson', 'alice@example.com', 'Premium'),
        ('CUST-102', 'Bob Smith', 'bob@example.com', 'Standard');

    INSERT INTO orders (order_id, customer_id, product_name, status, delivery_date, amount_usd) VALUES
        ('ORD-9001', 'CUST-101', 'Smart Home Hub Pro', 'Shipped', '2026-11-05', 149.99),
        ('ORD-9002', 'CUST-101', 'Ultra HD Security Cam', 'Processing', '2026-11-12', 89.50),
        ('ORD-9003', 'CUST-102', 'Wireless Mesh Node', 'Delivered', '2026-10-28', 59.99);
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("PostgreSQL tables created and seed data inserted successfully.")

if __name__ == "__main__":
    init_postgres()