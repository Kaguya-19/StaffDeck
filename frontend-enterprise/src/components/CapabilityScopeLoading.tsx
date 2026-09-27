import * as Source from '@staffdeck/business-ui/FormalCapabilityScopeLoading';
import { FormalPrimitives } from '../business-ui/formal-primitives';
import type { ComponentProps } from 'react';
export * from '@staffdeck/business-ui/FormalCapabilityScopeLoading';
export default function CapabilityScopeLoading(props: ComponentProps<typeof Source.default>) { return <FormalPrimitives><Source.default {...props} /></FormalPrimitives>; }
