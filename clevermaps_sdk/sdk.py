import time
from collections import OrderedDict
from . import dwh, jobs, export, metadata, search, client, projects
from . import exceptions

class Sdk:

    def __init__(self, access_token, project_id=None, server_url="https://secure.clevermaps.io"):

        self.client = client.Client(access_token, server_url)

        if project_id:

            self.project_id = project_id

            self.projects = projects.Projects(self.client)
            self.project = projects.Project(self.client)
            self.queries = dwh.Queries(self.client, self.project_id)
            self.property_values = dwh.PropertyValues(self.client, self.project_id)
            self.available_datasets = dwh.AvailableDatasets(self.client, self.project_id)
            self.jobs = jobs.Jobs(self.client, self.project_id)
            self.job_detail = jobs.JobDetail(self.client, self.project_id)
            self.export_data = export.ExportData(self.client, self.project_id)
            self.metrics = metadata.Metrics(self.client, self.project_id)
            self.datasets = metadata.Datasets(self.client, self.project_id)
            self.search = search.Search(self.client, self.project_id)
        else:
            self.projects = projects.Projects(self.client)
            self.project = projects.Project(self.client)

    def _get_query_content(self, properties_names, metric_names, filter_by):

        metrics = []
        for m in metric_names:
            metrics.append({
                "id": m,
                "type": "metric",
                "metric": "/rest/projects/{}/md/metrics?name={}".format(self.project_id, m)
            })

        properties = []
        for prop in properties_names:
            properties.append(
                {
                    'id': prop.replace('.', '_'),
                    'type': 'property',
                    'value': prop
                }
            )

        query = {
            "properties": properties + metrics,
            "filterBy": filter_by
        }

        return query

    def query(self, config, limit=1000):

        query_content = self._get_query_content(config.get('properties', []),
                                                config.get('metrics', []),
                                                config.get('filter_by', []))

        location = self.queries.accept_queries(query_content, limit)
        res = self.queries.get_queries(location)

        res_content = res['content']

        # Response does not preserve properties order, fix it back
        props_order = [p['id'] for p in query_content['properties']]

        res_content_ordered = []
        for r in res_content:
            res_content_ordered.append(dict(OrderedDict((k, r['content'][k]) for k in props_order)))

        return res_content_ordered

    def get_property_values(self, property_name):

        location = self.property_values.accept_property_values(property_name)
        res = self.property_values.get_property_values(location)

        return res['content']

    def get_available_datasets(self, metric_name):

        res = self.available_datasets.get_available_datasets(metric_name)
        datasets = [dataset['name'] for dataset in res['content'][0]['availableDatasets'] if dataset]

        return datasets

    def export_to_csv(self, config):

        query_content = self._get_query_content(config['query'].get('properties', []),
                                                config['query'].get('metrics', []),
                                                config['query'].get('filter_by', []))

        job_resp = self.jobs.start_new_export_job(query_content, config['filename'], config['format'])

        while True:
            job_status = self.job_detail.get_job_status(job_resp['links'][0]['href'])

            if job_status['status'] == 'SUCCEEDED':
                print(job_status)
                return self.export_data.get_export_data(job_status['result']['exportResult'])
            elif job_status['status'] in ('FAILED', 'TIMED_OUT', 'ABORTED'):
                print(job_status)
                raise Exception(job_status['status'])

            time.sleep(5)
