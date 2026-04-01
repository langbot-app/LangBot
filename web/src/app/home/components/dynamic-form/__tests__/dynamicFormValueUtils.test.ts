import test from 'node:test';
import assert from 'node:assert/strict';
import { DynamicFormItemType } from '@/app/infra/entities/form/dynamic';
import {
  getDynamicFieldFallbackValue,
  normalizeDynamicFieldValue,
} from '../dynamicFormValueUtils';

test('prompt-editor falls back to a default system prompt row when value is missing', () => {
  const value = normalizeDynamicFieldValue(
    {
      id: 'prompt',
      name: 'prompt',
      label: { en_US: 'Prompt' },
      type: DynamicFormItemType.PROMPT_EDITOR,
      required: true,
      default: '',
    },
    undefined,
  );

  assert.deepEqual(value, [
    {
      role: 'system',
      content: '',
    },
  ]);
});

test('string-array falls back to an empty list when value is missing', () => {
  const value = normalizeDynamicFieldValue(
    {
      id: 'tags',
      name: 'tags',
      label: { en_US: 'Tags' },
      type: DynamicFormItemType.STRING_ARRAY,
      required: false,
      default: '',
    },
    undefined,
  );

  assert.deepEqual(value, []);
});

test('model-fallback-selector keeps a stable object shape for malformed values', () => {
  const value = normalizeDynamicFieldValue(
    {
      id: 'model',
      name: 'model',
      label: { en_US: 'Model' },
      type: DynamicFormItemType.MODEL_FALLBACK_SELECTOR,
      required: true,
      default: '',
    },
    'primary-model-id',
  );

  assert.deepEqual(value, {
    primary: 'primary-model-id',
    fallbacks: [],
  });
});

test('prompt-editor fallback helper returns a default system prompt row', () => {
  assert.deepEqual(
    getDynamicFieldFallbackValue(DynamicFormItemType.PROMPT_EDITOR),
    [
      {
        role: 'system',
        content: '',
      },
    ],
  );
});
