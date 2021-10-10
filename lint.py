#!/usr/bin/env python3
from gherkin.parser import Parser
import spacy
from glob import glob
import re
import sys

## 2 vollverben?
## böse and?
## Glossar


def get_instantiations(scenario):
    if 'examples' not in scenario:
        return []
    for example in scenario['examples']:
        keys = [column['value'] for column in example['tableHeader']['cells']]
        for row in example['tableBody']:
            yield {k:v for k,v in zip(keys, [cell['value'] for cell in row['cells']])}


def replace_uuid(text):
    """
    >>> replace_uuid('check container 742ba6c1-7213-4d80-bf0d-c5814b3501e4')
    'check container UUID'
    """
    return re.sub('[a-z0-9]{8}\-[a-z0-9]{4}\-[a-z0-9]{4}\-[a-z0-9]{4}\-[a-z0-9]{12}', 'UUID', text)


def remove_comments(text):
    """
    >>> remove_comments('is configured as green # nice color')
    'is configured as green '
    """
    if '#' in text:
        text, _ = text.split('#', maxsplit=1)
    return text


def replace_variables(text, instantiation):
    """
    >>> replace_variables('is <color>', dict(color='green'))
    'is green'
    """                  
    for var, value in instantiation.items():
        text = text.replace(f'<{var}>', value)
    return text


def has_verb(analysis, has_table=False, logging=None):
    if any(token.pos_ == 'VERB' for token in analysis):
        return True
    lemmas = [token.lemma_ for token in analysis]
    a = ' '.join(lemmas)
    b = ' '.join(token.pos_ for token in analysis)

    if 'AUX ADP' in b:
        return True  # is in
    if lemmas[-1] == 'be' and has_table:
        return True  # ending with a auxiliary verb is okay if a table follows
    if 'NOUN AUX PROPN' in b:
        return True  # if using a proper noun, it's okay to just have an auxiliary verb
    if 'NOUN AUX NUM' in b:
        return True  # if using a proper noun, it's okay to just have an auxiliary verb
    if re.search('PROPN AUX.*PROPN', b):
        return True
    if re.search('NOUN.*AUX.*NOUN', b):
        return True
    if re.search('NOUN.*AUX.*ADV', b):
        return True
    if re.search('PROPN.*AUX.*ADJ', b):
        return True
    if re.search('NOUN.*AUX.*ADJ', b):
        return True
    if logging:
        logging('has no verb')
    return False


def has_correct_tense(analysis, step_type, logging=None):
    possible_tenses = set([tense for token in analysis if token.morph.get('Tense') for tense in token.morph.get('Tense')])
    if not possible_tenses:
        return True # TODO: Logging
    expected_tenses = dict(Given=['Past', 'Pres'], When=['Pres'], Then=['Pres'])[step_type]
    # TODO: support present progressive

    if not any(tense in possible_tenses for tense in expected_tenses):
        if logging:
            logging(f'has wrong tense. expected {" ".join(expected_tenses)} tense ({step_type.lower()}-step), but got {" ".join(possible_tenses)}')
        return False
    return True


if __name__ == '__main__':
    parser = Parser()
    nlp = spacy.load("en_core_web_trf")
    broken = False
    for path in glob('corpus/*.feature'):
        with open(path, 'r') as file:
            feature = parser.parse(file.read())
            for child in feature['feature']['children']:
                key = 'scenario' if 'scenario' in child else 'background'
                for instantiation in get_instantiations(child[key]):
                    step_type = 'Given'
                    for step in child[key]['steps']:
                        if step['keyword'].strip().lower() == 'when':
                            step_type = 'When'
                        if step['keyword'].strip().lower() == 'then':
                            step_type = 'Then'
                        
                        text = remove_comments(replace_uuid(replace_variables(step['text'], instantiation)))

                        def logging(issue):
                            print(f'{path} ({child[key]["location"]["line"]}): Step "{text}" - {issue}', file=sys.stderr)

                        analysis = nlp(text)
                        if not has_verb(analysis, has_table='dataTable' in step, logging=logging):
                            broken = True
                        if not has_correct_tense(analysis, step_type=step_type, logging=logging):
                            broken = True

    if broken:
        print('issues found.', file=sys.stderr)
        sys.exit(1)
