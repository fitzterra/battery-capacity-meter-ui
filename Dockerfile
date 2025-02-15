# We start off on the slim Python V311 Debain base
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /code

# Copy the file with the requirements to the /code directory.
# Copy only the file with the requirements first, not the rest of the code.
# As this file doesn't change often, Docker will detect it and use the cache
# for this step, enabling the cache for the next step too.
COPY ./requirements.txt /code/requirements.txt

# Install the required dependencies
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy the ./app directory inside the /code directory.
# As this has all the code which is what changes most frequently the Docker
# cache won't be used for this or any following steps easily.
# So, it's important to put this near the end of the Dockerfile, to optimize
# the container image build times.
COPY ./app /code/app

# Command to run the FastAPI app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
