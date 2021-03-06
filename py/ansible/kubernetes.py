#!/usr/bin/python
## Ansible Kubernetes module with token based authentication
## TODO: Add a function to check if the provided resource is already present in the cluster


from ansible.module_utils.basic import *
import requests
import json
import yaml


DOCUMENTATION = """
---
Module: kubernetes
Short_description: Manage kubernetes resources with ansible and token based authentication
Supported resources for the moment:

deployment,
configmap,
secret,
service,
persistentvolumeclaim,
statefulset,
namespace


Notes:
There are two ways to provide object data for the moment: kubernetes yaml definition file, or yaml formatted data
"""


EXAMPLES = """
#Create deployment from yaml file

- name: My test module
  kubernetes:
    api_address: https://api_address:PORT
    token: YOUR_TOKEN_HERE
    type: deployment
    state: present
    file: files/nginx.yml

#Create configmap from yaml file

- name: My test module
  kubernetes:
    api_address: https://api_address:PORT
    token: YOUR_TOKEN_HERE
    type: configmap
    state: present
    file: files/config.yml

# Delete resources

- name: My test module
  kubernetes:
    api_address: https://api_address:PORT
    token: YOUR_TOKEN_HERE
    type: deployment                                 ## Type may be deployment, configmap
    state: absent
    name: ansible-test                               ## Name is mandatory to be able to find the resource as well as type

# Inline data provided

  - name: Namespace
    my-kubernetes:
      api_address: https://api_address:PORT
      token: TOKEN-HERE
      type: deployment
      state: present
      data:
        apiVersion: apps/v1
        kind: Deployment
        metadata:
          labels:
            run: nginx
          name: nginx
          namespace: my-test
        spec:
          replicas: 1
          selector:
            matchLabels:
              run: nginx
          template:
            metadata:
              labels:
                run: nginx
            spec:
              containers:
              - image: nginx
                name: test



"""




class connection():

    def __init__(self, data):
        self.read_endpoints = {
                "deployment": "/apis/extensions/v1beta1/deployments",
                "configmap": "/api/v1/configmaps/",
                "secret": "/api/v1/secrets/",
                "service": "/api/v1/services/",
                "persistentvolumeclaim": "/api/v1/persistentvolumeclaims/",
                "statefulset": "/apis/apps/v1/statefulsets",
                "namespace": "/api/v1/namespaces/",
        }

        self.write_endpoints = {
                "deployment": "/apis/apps/v1/namespaces/",
                "configmap": "/api/v1/namespaces/",
                "secret": "/api/v1/namespaces/",
                "service": "/api/v1/namespaces/",
                "persistentvolumeclaim": "/api/v1/namespaces/",
                "statefulset": "/apis/apps/v1/namespaces/",
                "namespace": "/api/v1/namespaces"
        }
        self.headers = {
                "Authorization": "",
                "Accept": "application/json",
                "Content-Type": "application/json"
        }
        self.api_address = data['api_address']
        self.token = data['token']
        self.kind = data['type']
        self.state = data['state']
        self.headers['Authorization'] = "Bearer " + self.token


    def present(self, data):
        ### Check if inline data is provided or yaml file location
        if data.get('data'):
            obj = data['data']
            self.obj_data = json.loads(json.dumps(obj))
            ## Check if resource is cluster scoped (namespace) or other ,
            ## if other check if namespace parameter is provided , if not assume default
            if data['type'] != 'namespace':
                try:
                    self.namespace = self.obj_data['metadata']['namespace']
                except KeyError:
                    self.namespace = "default"
        elif data.get('file'):
            file_path = data['file']
            with open(file_path, 'r') as f:
                obj = f.read()
            self.obj_data = json.loads(json.dumps(yaml.safe_load(obj)))
            ## Same check as above when reading yaml from file
            if data['type'] != 'namespace':
                try:
                    self.namespace = self.obj_data['metadata']['namespace']
                except KeyError:
                    self.namespace = "default"
        ## If neither data or file is provided fail the run
        else:
            has_changed = False
            is_error = True
            meta = "Please provide eith data field with yaml formated kubernetes data or file with path to the yaml file"
            return (has_changed, meta, is_error)

        ### Check the kind of the object to craft url
        if self.kind == "deployment":
            url = self.api_address + self.write_endpoints[self.kind] + self.namespace + "/deployments"
        elif self.kind == "configmap":
            url = self.api_address + self.write_endpoints[self.kind] + self.namespace + "/configmaps"
        elif self.kind == "secret":
            url = self.api_address + self.write_endpoints[self.kind] + self.namespace + "/secrets"
        elif self.kind == "service":
            url = self.api_address + self.write_endpoints[self.kind] + self.namespace + "/services"
        elif self.kind == "persistentvolumeclaim":
            url = self.api_address + self.write_endpoints[self.kind] + self.namespace + "/persistentvolumeclaims"
        elif self.kind == "statefulset":
            url = self.api_address + self.write_endpoints[self.kind] + self.namespace + "/statefulsets"
        elif self.kind == "namespace":
            url = self.api_address + self.write_endpoints[self.kind]

        requests.packages.urllib3.disable_warnings()
        response = requests.post(url, headers=self.headers, data=json.dumps(self.obj_data), verify=False)

        ## Check the status code to determine success or failure
        if response.status_code == 201 or response.status_code == 200:
            has_changed = True
            meta = response.json()
            is_error = False
            return (has_changed, meta, is_error)
        else:
            has_changed = False
            meta = response.json()
            is_error = True
            return (has_changed, meta, is_error)


    def absent(self, data):
        ## Check if resource name is provided for deletion , if not fail
        if data.get('name'):
            self.obj_name = data['name']
        else:
            has_changed = False
            meta = "Please provide object name for absent state"
            is_error = True
            return (has_changed, meta, is_error)
        ## Get all resources of the provided kind to filter the correct one based on name
        check_url = self.api_address + self.read_endpoints[self.kind]
        requests.packages.urllib3.disable_warnings()
        reply = requests.get(check_url, headers=self.headers ,verify=False)


        all_objects = reply.json()
        ## Extract the delete url for the specified object
        for item in all_objects['items']:
            name = item['metadata']['name']

            url = self.api_address + item['metadata']['selfLink']
            if name == self.obj_name:
                ## If the resource is deployment or statefulset add query parameter propagationPolicy so all child resources are deleted as well
                if self.kind == 'deployment' or self.kind == 'statefulset':
                    delete = requests.delete(url + "?propagationPolicy=Foreground", headers=self.headers, verify=False)
                else:
                    delete = requests.delete(url, headers=self.headers, verify=False)
                has_changed = True
                meta = delete.json()
                is_error = False
                return (has_changed, meta, is_error)
        ## If resource with no such name is found fail
        has_changed = False
        meta = "Object with name: {} not found..".format(self.obj_name)
        is_error = True
        return (has_changed, meta, is_error)





def main():
    ### Arguments for our kubernetes module
    arguments = {
        "api_address": {"required": True, "type": "str"},
        "token": {"required": True, "type": "str"},
        "type": {
             "required": True,
             "type": "str",
             "choices": ["deployment", "configmap", "secret", "service", "persistentvolumeclaim", "statefulset", "namespace"]
        },
        "state": {
             "default": "present",
             "type": "str",
             "choices": ["present", "absent"]
        },
        "data": {"required": False, "type": "dict"},
        "file": {"required": False, "type": "str"},
        "name": {"required": False, "type": "str"},
    }

    ## Add the arguments for the module
    module = AnsibleModule(argument_spec=arguments)
    ## Init our class
    con = connection(module.params)

    ### Choose function based on type and state declared , #TODO: refactor this as the functions are only two
    choice_map = {
        "deployment": {
                "present": con.present,
                "absent": con.absent,
         },
        "configmap": {
                "present": con.present,
                "absent": con.absent,
         },
        "secret" : {
                "present": con.present,
                "absent": con.absent,
        },
        "service" : {
                "present": con.present,
                "absent": con.absent,
        },
        "persistentvolumeclaim" : {
                "present": con.present,
                "absent": con.absent,
        },
        "statefulset" : {
                "present": con.present,
                "absent": con.absent,
        },
        "namespace" : {
                "present": con.present,
                "absent": con.absent,
        },

    }

    ## Choose which function to use based on type and state , must be refactored at some time
    has_changed, result, is_error = choice_map.get(module.params['type'])[module.params['state']](module.params)
    ### Check the execution status
    if is_error == False:
        module.exit_json(changed=has_changed, meta=result)
    else:
        module.fail_json(msg="Error received: ", meta=result)



if __name__ == '__main__':
    main()
