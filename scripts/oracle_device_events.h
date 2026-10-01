#ifndef JFG_ORACLE_DEVICE_EVENTS_H
#define JFG_ORACLE_DEVICE_EVENTS_H
/* Only private interpreter oracles call this host-only observer. */
void jfg_oracle_events_begin(void);
void jfg_oracle_events_instruction(unsigned int opcode);
void jfg_oracle_events_cached_instruction(void);
void jfg_oracle_events_enter_dispatch(void);
void jfg_oracle_events_dispatch(int type, unsigned int deadline);
void jfg_oracle_events_accept(void);
void jfg_oracle_events_leave_dispatch(void);
#endif
