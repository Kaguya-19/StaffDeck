import * as Source from '@staffdeck/business-ui/FormalModelConfigDropdown';
import { FormalPrimitives } from '../business-ui/formal-primitives';
import type { ComponentProps } from 'react';
export * from '@staffdeck/business-ui/FormalModelConfigDropdown';
export function ModelConfigDropdown(props: ComponentProps<typeof Source.ModelConfigDropdown>) { return <FormalPrimitives><Source.ModelConfigDropdown {...props} /></FormalPrimitives>; }
