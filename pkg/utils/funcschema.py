import re
import inspect
import typing


def get_func_schema(function: typing.Callable) -> dict:
    """
    Return the data schema of a function.
    {
        "function": function,
        "description": "function description",
        "parameters": {
            "type": "object",
            "properties": {
                "parameter_a": {
                    "type": "str",
                    "description": "parameter_a description"
                },
                "parameter_b": {
                    "type": "int",
                    "description": "parameter_b description"
                },
                "parameter_c": {
                    "type": "str",
                    "description": "parameter_c description",
                    "enum": ["a", "b", "c"]
                },
            },
            "required": ["parameter_a", "parameter_b"]
        }
    }
    """
    func_doc = function.__doc__
    # Google Style Docstring
    if func_doc is None:
        raise Exception('Function {} has no docstring.'.format(function.__name__))
    func_doc = func_doc.strip().replace('    ', '').replace('\t', '')
    # extract doc of args from docstring
    doc_spt = func_doc.split('\n\n')
    desc = doc_spt[0]
    args = doc_spt[1] if len(doc_spt) > 1 else ''
    # returns = doc_spt[2] if len(doc_spt) > 2 else ""

    # extract args
    # delete the first line of args
    arg_lines = args.split('\n')[1:]
    # arg_doc_list = re.findall(r'(\w+)(\((\w+)\))?:\s*(.*)', args)
    args_doc = {}
    for arg_line in arg_lines:
        doc_tuple = re.findall(r'(\w+)(\(([\w\[\]]+)\))?:\s*(.*)', arg_line)
        if len(doc_tuple) == 0:
            continue
        args_doc[doc_tuple[0][0]] = doc_tuple[0][3]

    # extract returns
    # return_doc_list = re.findall(r'(\w+):\s*(.*)', returns)

    params = enumerate(inspect.signature(function).parameters.values())
    parameters = {
        'type': 'object',
        'required': [],
        'properties': {},
    }

    for i, param in params:
        # 排除 self, query
        if param.name in ['self', 'query']:
            continue

        param_type = param.annotation.__name__

        type_name_mapping = {
            'str': 'string',
            'int': 'integer',
            'float': 'number',
            'bool': 'boolean',
            'list': 'array',
            'dict': 'object',
        }

        if param_type in type_name_mapping:
            param_type = type_name_mapping[param_type]

        parameters['properties'][param.name] = {
            'type': param_type,
            'description': args_doc[param.name],
        }

        # add schema for array
        if param_type == 'array':
            # extract type of array, the int of list[int]
            # use re
            array_type_tuple = re.findall(r'list\[(\w+)\]', str(param.annotation))

            array_type = 'string'

            if len(array_type_tuple) > 0:
                array_type = array_type_tuple[0]

            if array_type in type_name_mapping:
                array_type = type_name_mapping[array_type]

            parameters['properties'][param.name]['items'] = {
                'type': array_type,
            }

        if param.default is inspect.Parameter.empty:
            parameters['required'].append(param.name)

    return {
        'function': function,
        'description': desc,
        'parameters': parameters,
    }
