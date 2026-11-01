# AWS Glue 5.1 image, plus the Python libraries our code needs that Glue 5.1 does not ship:
#   PyYAML     config files (the jobs)
#   streamlit  the dashboard, which runs locally in this same image so it can read the Iceberg lake with Spark
#              (in AWS the dashboard uses its own small image, dashboard/Dockerfile, and reads with Athena)
FROM public.ecr.aws/glue/aws-glue-libs:5.1.0

USER root
RUN pip3 install --no-cache-dir PyYAML==6.0.3 streamlit==1.66.1
USER hadoop
