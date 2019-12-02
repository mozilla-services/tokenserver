# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest

from pyramid.config import Configurator


class TestNodeTypeClassifier(unittest.TestCase):

    DEFAULT_SETTINGS = {  # noqa; identation below is non-standard
        "tokenserver.backend":
            "tokenserver.assignment.memorynode.MemoryNodeAssignmentBackend",
        "oauth.backend":
            "tokenserver.verifiers.RemoteOAuthVerifier",
        "tokenserver.secrets.backend":
            "mozsvc.secrets.FixedSecrets",
        "tokenserver.secrets.secrets":
            "steve-let-the-dogs-out",
    }

    def _make_classifier(self, settings={}):
        all_settings = self.DEFAULT_SETTINGS.copy()
        all_settings.update(settings)
        config = Configurator(settings=all_settings)
        config.include("tokenserver")
        config.commit()
        return config.registry.settings['tokenserver.node_type_classifier']

    def test_no_patterns(self):
        classifier = self._make_classifier()
        self.assertEquals(classifier(''), None)
        self.assertEquals(classifier('https://example.com'), None)

    def test_error_if_not_a_list(self):
        with self.assertRaises(ValueError):
            self._make_classifier({
                'tokenserver.node_type_patterns': 'foo:*.bar.com',

            })

    def test_error_if_pattern_has_no_label(self):
        with self.assertRaises(ValueError):
            self._make_classifier({
                'tokenserver.node_type_patterns': [
                    ':*.bar.com',
                ],
            })

    def test_error_if_duplicate_pattern_label(self):
        with self.assertRaises(ValueError):
            self._make_classifier({
                'tokenserver.node_type_patterns': [
                    'foo:*.foo.com',
                    'foo:*.bar.com',
                ],
            })

    def test_pattern_matching(self):
        classifier = self._make_classifier({
            'tokenserver.node_type_patterns': [
                'foo:*.foo.com',
                'bar:*.bar.com',
            ],
        })
        self.assertEquals(classifier(''), None)
        self.assertEquals(classifier('https://example.com'), None)
        self.assertEquals(classifier('https://example.foo.com'), 'foo')
        self.assertEquals(classifier('https://example.bar.com'), 'bar')

    def test_precedence_order(self):
        classifier = self._make_classifier({
            'tokenserver.node_type_patterns': [
                'foo1:*foo.foo.com',
                'foo2:*.foo.com',
            ],
        })
        self.assertEquals(classifier(''), None)
        self.assertEquals(classifier('https://foo.com'), None)
        self.assertEquals(classifier('https://example.foo.com'), 'foo2')
        self.assertEquals(classifier('https://foo.foo.com'), 'foo1')
