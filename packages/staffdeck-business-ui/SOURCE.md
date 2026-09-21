# Source Map

`SopVersionDetailDialog.tsx` is extracted from the `VersionDetailDialog`
function in `frontend-enterprise/src/pages/SkillsPage.tsx` on the portable
StaffDeck baseline. The source interaction is preserved: the selected version
is optional, the dialog closes through the host callback, the version/domain/
status/call-rate/update fields remain visible, and the serialized SOP content
remains inspectable in the detail view.

The extraction delta is limited to the host boundary: StaffDeck's Radix
`Dialog` primitives, icon aliases, `DetailField`, and local formatting helpers
are replaced by package-local render primitives and injected labels. No API
call, draft mutation, or alternate SOP workflow is implemented in this slice.

PilotDeck consumes the checked-in release snapshot at
`ui/src/composition/modules/staffdeck/vendor/SopVersionDetailDialog.tsx`.
