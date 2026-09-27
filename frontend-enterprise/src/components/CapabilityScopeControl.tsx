import * as Source from '@staffdeck/business-ui/FormalCapabilityScopeControl';
import { FormalPrimitives } from '../business-ui/formal-primitives';
import type { ComponentProps } from 'react';
export * from '@staffdeck/business-ui/FormalCapabilityScopeControl';
export function CapabilityScopeBadge(props: ComponentProps<typeof Source.CapabilityScopeBadge>) { return <FormalPrimitives><Source.CapabilityScopeBadge {...props} /></FormalPrimitives>; }
export function CapabilityScopeControl(props: ComponentProps<typeof Source.CapabilityScopeControl>) { return <FormalPrimitives><Source.CapabilityScopeControl {...props} /></FormalPrimitives>; }
