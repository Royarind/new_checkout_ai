# Use the official Playwright Python image
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium is usually sufficient, but installing all ensures compatibility)
RUN playwright install chromium

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 8050

# Command to run the application
CMD ["python", "ui/app.py"]
