# AWS Glue 5.1 image, plus the one Python library our jobs need that Glue 5.1 does not ship.
FROM public.ecr.aws/glue/aws-glue-libs:5.1.0

USER root
RUN pip3 install --no-cache-dir PyYAML==6.0.3
USER hadoop