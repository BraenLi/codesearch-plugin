"""
Sample C code for testing codesearch-plugin.
"""

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Memory allocation wrapper with error handling
void* malloc_wrapper(size_t size) {
    void* ptr = malloc(size);
    if (!ptr) {
        fprintf(stderr, "Memory allocation failed: size=%zu\n", size);
        exit(1);
    }
    return ptr;
}

// Safe calloc that checks for overflow
void* safe_calloc(size_t nmemb, size_t size) {
    if (nmemb == 0 || size == 0) {
        return NULL;
    }

    // Check for overflow
    if (nmemb > SIZE_MAX / size) {
        fprintf(stderr, "Integer overflow in calloc\n");
        exit(1);
    }

    return calloc(nmemb, size);
}

// Realloc wrapper with error checking
void* safe_realloc(void* ptr, size_t size) {
    void* new_ptr = realloc(ptr, size);
    if (!new_ptr && size != 0) {
        fprintf(stderr, "Memory reallocation failed\n");
        exit(1);
    }
    return new_ptr;
}

// Safe free that handles NULL
void safe_free(void* ptr) {
    if (ptr != NULL) {
        free(ptr);
    }
}

// String duplication with error handling
char* safe_strdup(const char* str) {
    if (str == NULL) {
        return NULL;
    }

    size_t len = strlen(str) + 1;
    char* dup = malloc_wrapper(len);
    memcpy(dup, str, len);
    return dup;
}

// Point structure for 2D coordinates
typedef struct {
    int x;
    int y;
} Point;

// Rectangle structure
typedef struct {
    Point top_left;
    Point bottom_right;
} Rectangle;

// Game object with position and velocity
typedef struct {
    Point position;
    Point velocity;
    int health;
    char* name;
} GameObject;

// Create a new game object
GameObject* create_game_object(int x, int y, const char* name) {
    GameObject* obj = malloc_wrapper(sizeof(GameObject));
    obj->position.x = x;
    obj->position.y = y;
    obj->velocity.x = 0;
    obj->velocity.y = 0;
    obj->health = 100;
    obj->name = safe_strdup(name);
    return obj;
}

// Destroy a game object
void destroy_game_object(GameObject* obj) {
    if (obj) {
        safe_free(obj->name);
        safe_free(obj);
    }
}

// Error codes for the game engine
typedef enum {
    SUCCESS = 0,
    ERROR_MEMORY = 1,
    ERROR_INVALID_PARAM = 2,
    ERROR_OUT_OF_BOUNDS = 3,
    ERROR_NOT_FOUND = 4
} ErrorCode;

// Result type for functions that can fail
typedef struct {
    ErrorCode code;
    union {
        int int_value;
        void* ptr_value;
    } data;
} Result;

// Initialize a point
void point_init(Point* p, int x, int y) {
    if (p) {
        p->x = x;
        p->y = y;
    }
}

// Calculate distance squared between two points
int point_distance_squared(const Point* a, const Point* b) {
    int dx = a->x - b->x;
    int dy = a->y - b->y;
    return dx * dx + dy * dy;
}

// Check if point is inside rectangle
int rectangle_contains(const Rectangle* rect, const Point* p) {
    return p->x >= rect->top_left.x &&
           p->x <= rect->bottom_right.x &&
           p->y >= rect->top_left.y &&
           p->y <= rect->bottom_right.y;
}

// Main entry point
int main(int argc, char* argv[]) {
    printf("Memory Management Demo\n");

    // Allocate some memory
    int* numbers = malloc_wrapper(10 * sizeof(int));

    // Use the memory
    for (int i = 0; i < 10; i++) {
        numbers[i] = i * i;
        printf("numbers[%d] = %d\n", i, numbers[i]);
    }

    // Free the memory
    safe_free(numbers);

    // Create a game object
    GameObject* player = create_game_object(100, 200, "Player");
    printf("Created player at (%d, %d)\n",
           player->position.x, player->position.y);

    // Clean up
    destroy_game_object(player);

    return 0;
}
