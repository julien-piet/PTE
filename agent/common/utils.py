#
# Copyright 2025 Project Team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import logging
from agent.providers.provider import ModelProvider


def get_mcp_logger(name = 'mcp.log'):
    log_path = os.path.expanduser(f"./logs/{name}")
    log_dir = os.path.dirname(log_path)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    logging.basicConfig(filename=log_path, level=logging.DEBUG, force=True)
    logger = logging.getLogger("mcp.server.lowlevel.server")
    
    return logger

def get_llm(config, model_provider = None, model_name = None):
    provider = ModelProvider(config, model_provider, model_name)
    llm =  provider.get_llm_model_provider()
    return llm

def get_llm_signature(config, model_provider = None, model_name = None):
    provider = ModelProvider(config, model_provider, model_name)
    llm = provider.llm_provider + ":" + provider.model_name
    return llm

def compare_dicts(dict1, dict2):
    if dict1 == dict2:
        return True

    keys1 = set(dict1.keys())
    keys2 = set(dict2.keys())

    only_in_1 = keys1 - keys2
    only_in_2 = keys2 - keys1
    common = keys1 & keys2

    if only_in_1:
        print("Keys only in dict1:", only_in_1)
    if only_in_2:
        print("Keys only in dict2:", only_in_2)

    for key in common:
        if dict1[key] != dict2[key]:
            print(f"Different value for key '{key}': dict1 has {dict1[key]}, dict2 has {dict2[key]}")

    return False
