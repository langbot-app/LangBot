/**
 * Workflow Node Configuration Types
 * 
 * This module defines the types used for node configuration metadata.
 * It extends the existing dynamic form system to support workflow-specific features.
 */

import { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';
import { I18nObject } from '@/app/infra/entities/common';
import { NodeCategory, PortDefinition } from '@/app/infra/entities/workflow';

/**
 * Extended port configuration with additional metadata
 */
export interface ExtendedPortDefinition extends PortDefinition {
  label?: I18nObject;
}

/**
 * Node configuration metadata
 * Defines all aspects of a node type including its appearance, ports, and configuration options
 */
export interface NodeConfigMeta {
  /** Unique node type identifier */
  nodeType: string;
  
  /** Display name for the node */
  label: I18nObject;
  
  /** Description of what the node does */
  description: I18nObject;
  
  /** Icon name (from lucide-react) */
  icon: string;
  
  /** Node category for organization */
  category: NodeCategory;
  
  /** Color for the node header */
  color?: string;
  
  /** Input port definitions */
  inputs: ExtendedPortDefinition[];
  
  /** Output port definitions */
  outputs: ExtendedPortDefinition[];
  
  /** Configuration schema using the dynamic form system */
  configSchema: IDynamicFormItemSchema[];
  
  /** Default configuration values */
  defaultConfig?: Record<string, unknown>;
  
  /** Whether this node can be the starting point of a workflow */
  isEntryPoint?: boolean;
  
  /** Maximum number of this node type allowed in a workflow (undefined = unlimited) */
  maxInstances?: number;
  
  /** Documentation URL */
  docsUrl?: string;
}

/**
 * Registry of all node configurations by type
 */
export type NodeConfigRegistry = Record<string, NodeConfigMeta>;

/**
 * Helper function to create a consistent port definition
 */
export function createPort(
  name: string,
  type: string,
  options?: {
    description?: string;
    required?: boolean;
    label?: I18nObject;
  }
): ExtendedPortDefinition {
  return {
    name,
    type,
    description: options?.description,
    required: options?.required ?? false,
    label: options?.label,
  };
}

/**
 * Helper function to create input port
 */
export function createInput(
  name: string,
  type: string,
  options?: {
    description?: string;
    required?: boolean;
    label?: I18nObject;
  }
): ExtendedPortDefinition {
  return createPort(name, type, { ...options, required: options?.required ?? true });
}

/**
 * Helper function to create output port
 */
export function createOutput(
  name: string,
  type: string,
  options?: {
    description?: string;
    label?: I18nObject;
  }
): ExtendedPortDefinition {
  return createPort(name, type, { ...options, required: false });
}
