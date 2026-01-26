import { UUID } from 'uuidjs';
import {
  IDynamicFormItemSchema,
  DynamicFormItemType,
} from '@/app/infra/entities/form/dynamic';
import { JSONSchema, JSONSchemaProperty } from '@/app/infra/entities/api';

/**
 * Convert a JSON Schema property type to DynamicFormItemType
 */
function mapJsonSchemaType(
  prop: JSONSchemaProperty,
): DynamicFormItemType {
  // Handle enum as select
  if (prop.enum && prop.enum.length > 0) {
    return DynamicFormItemType.SELECT;
  }

  switch (prop.type) {
    case 'integer':
      return DynamicFormItemType.INT;
    case 'number':
      return DynamicFormItemType.FLOAT;
    case 'boolean':
      return DynamicFormItemType.BOOLEAN;
    case 'string':
      return DynamicFormItemType.STRING;
    case 'array':
      return DynamicFormItemType.STRING_ARRAY;
    default:
      return DynamicFormItemType.STRING;
  }
}

/**
 * Get default value based on type
 */
function getDefaultValue(
  prop: JSONSchemaProperty,
): string | number | boolean | unknown[] {
  if (prop.default !== undefined) {
    return prop.default as string | number | boolean | unknown[];
  }

  switch (prop.type) {
    case 'integer':
    case 'number':
      return 0;
    case 'boolean':
      return false;
    case 'array':
      return [];
    default:
      return '';
  }
}

/**
 * Convert JSON Schema to IDynamicFormItemSchema array
 * This allows using the existing DynamicFormComponent with JSON Schema data
 */
export function jsonSchemaToFormItems(
  schema: JSONSchema | undefined,
): IDynamicFormItemSchema[] {
  if (!schema || !schema.properties) {
    return [];
  }

  const requiredFields = schema.required || [];
  const items: IDynamicFormItemSchema[] = [];

  for (const [name, prop] of Object.entries(schema.properties)) {
    const formItem: IDynamicFormItemSchema = {
      id: UUID.generate(),
      name,
      label: { en_US: name, zh_Hans: name },
      description: prop.description
        ? { en_US: prop.description, zh_Hans: prop.description }
        : undefined,
      type: mapJsonSchemaType(prop),
      required: requiredFields.includes(name),
      default: getDefaultValue(prop),
    };

    // Handle enum options for select type
    if (prop.enum && prop.enum.length > 0) {
      formItem.options = prop.enum.map((value) => ({
        name: String(value),
        label: { en_US: String(value), zh_Hans: String(value) },
      }));
    }

    items.push(formItem);
  }

  return items;
}

/**
 * Extract default values from JSON Schema
 */
export function getDefaultValuesFromSchema(
  schema: JSONSchema | undefined,
): Record<string, unknown> {
  if (!schema || !schema.properties) {
    return {};
  }

  const defaults: Record<string, unknown> = {};

  for (const [name, prop] of Object.entries(schema.properties)) {
    defaults[name] = getDefaultValue(prop);
  }

  return defaults;
}
