#ifndef CELESTE_H_
#define CELESTE_H_

#ifdef __cplusplus
#define _Bool bool
extern "C" {
#endif

typedef enum {
	CELESTE_P8_MUSIC, CELESTE_P8_SPR, CELESTE_P8_BTN, CELESTE_P8_SFX,
	CELESTE_P8_PAL, CELESTE_P8_PAL_RESET, CELESTE_P8_CIRCFILL, CELESTE_P8_PRINT,
	CELESTE_P8_RECTFILL, CELESTE_P8_LINE, CELESTE_P8_MGET, CELESTE_P8_CAMERA,
	CELESTE_P8_FGET, CELESTE_P8_MAP
} CELESTE_P8_CALLBACK_TYPE;

typedef _Bool Celeste_P8_bool_t;
typedef int (*Celeste_P8_cb_func_t) (CELESTE_P8_CALLBACK_TYPE calltype, ...);

#define ROOM_TILE_COUNT 16
#define ROOM_TILE_STRIDE (ROOM_TILE_COUNT * 2)
#define MAP_ROOM_COLUMNS 8
#define MAP_ROOM_ROWS 4
#define MAP_TILE_WIDTH (MAP_ROOM_COLUMNS * ROOM_TILE_STRIDE)
#define MAP_TILE_HEIGHT (MAP_ROOM_ROWS * ROOM_TILE_COUNT)
#define LOGICAL_TILE_SIZE 8
#define TILE_SIZE 15
#define LOGICAL_ROOM_SIZE (ROOM_TILE_COUNT * LOGICAL_TILE_SIZE)
#define SCREEN_SIZE (ROOM_TILE_COUNT * TILE_SIZE)
#define WIDE_SCREEN_SIZE 400
#define LOGICAL_WIDE_SCREEN_MARGIN (((WIDE_SCREEN_SIZE - SCREEN_SIZE) * LOGICAL_TILE_SIZE + 2*TILE_SIZE - 1) / (2*TILE_SIZE))
#define LOGICAL_WIDE_SCREEN_LEFT (-LOGICAL_WIDE_SCREEN_MARGIN)
#define LOGICAL_WIDE_SCREEN_RIGHT (LOGICAL_ROOM_SIZE + LOGICAL_WIDE_SCREEN_MARGIN)

extern void Celeste_P8_set_call_func(Celeste_P8_cb_func_t func);
extern void Celeste_P8_set_rndseed(unsigned seed);
extern void Celeste_P8_init(void);
extern void Celeste_P8_update(void);
extern void Celeste_P8_draw(void);
extern int Celeste_P8_get_level_index(void);
extern void Celeste_P8_load_level(int level);

extern void Celeste_P8__DEBUG(void); //debug functionality

//state functionality
size_t Celeste_P8_get_state_size(void);
void Celeste_P8_save_state(void* st);
void Celeste_P8_load_state(const void* st);

#ifdef __cplusplus
} //extern "C"
#endif

#endif
