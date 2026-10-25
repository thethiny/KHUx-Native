// Adapters: call a native function with the argument words the rewrite passes (the ARM EABI layout: r0-r3 then the
// stack, as one list). Used by the generated game -> engine table (tools/gen_adapters.py).
//
// Word layout (AAPCS, softfp - floats travel as bits in core registers):
//   [sret]  a hidden result pointer first, for a class result > 4 bytes or not trivially copyable
//   [this]  member functions
//   params  pointers / references / <= 32-bit scalars: 1 word; 64-bit scalars: 2 words at an even index;
//           trivially copyable classes by value: their bytes (8-aligned if their alignment is 8);
//           other classes by value: a pointer to a copy (the Itanium ABI's invisible reference)
#pragma once

#include <cstdint>
#include <cstring>
#include <new>
#include <tuple>
#include <type_traits>
#include <utility>

namespace khux {

template <class T> using Bare = std::remove_cv_t<std::remove_reference_t<T>>;

template <class P> P word_arg(const uint32_t *a, int &k) {
    using T = Bare<P>;
    if constexpr (std::is_reference_v<P>) {
        return *reinterpret_cast<T *>(uintptr_t(a[k++]));
    } else if constexpr (std::is_pointer_v<T> || std::is_null_pointer_v<T>) {
        return reinterpret_cast<T>(uintptr_t(a[k++]));
    } else if constexpr ((std::is_arithmetic_v<T> || std::is_enum_v<T>) && sizeof(T) == 8) {
        k = (k + 1) & ~1;
        T v;
        std::memcpy(&v, &a[k], 8);
        k += 2;
        return v;
    } else if constexpr (std::is_same_v<T, float>) {
        T v;
        std::memcpy(&v, &a[k++], 4);
        return v;
    } else if constexpr (std::is_same_v<T, bool>) {
        return (a[k++] & 0xFF) != 0;
    } else if constexpr (std::is_arithmetic_v<T> || std::is_enum_v<T>) {
        return static_cast<T>(a[k++]);
    } else if constexpr (!std::is_trivially_copyable_v<T>) {
        return *reinterpret_cast<T *>(uintptr_t(a[k++]));
    } else {
        if (alignof(T) >= 8) k = (k + 1) & ~1;
        T v;
        std::memcpy(static_cast<void *>(&v), &a[k], sizeof(T));
        k += int((sizeof(T) + 3) / 4);
        return v;
    }
}

template <class R> constexpr bool is_sret() {
    using T = Bare<R>;
    if constexpr (std::is_void_v<R> || std::is_reference_v<R>) return false;
    else if constexpr (std::is_class_v<T> || std::is_union_v<T>) return !std::is_trivially_copyable_v<T> || sizeof(T) > 4;
    else return false;
}

template <class R, class F> uint64_t result(void *sret, F &&call) {
    using T = Bare<R>;
    if constexpr (std::is_void_v<R>) {
        call();
        return 0;
    } else if constexpr (std::is_reference_v<R>) {
        return uint64_t(uintptr_t(&call()));
    } else if constexpr (is_sret<R>()) {
        new (sret) T(call());
        return uint64_t(uintptr_t(sret));
    } else if constexpr (std::is_pointer_v<T>) {
        return uint64_t(uintptr_t(call()));
    } else {
        T v = call();
        uint64_t bits = 0;
        std::memcpy(&bits, &v, sizeof(T) <= 8 ? sizeof(T) : 8);
        return bits;
    }
}

template <class... P> std::tuple<P...> word_args(const uint32_t *a, int &k) {
    return std::tuple<P...>{word_arg<P>(a, k)...};      // braced: evaluated left to right
}

// member function
template <class... P, class R, class C> uint64_t adapt(R (C::*f)(P...), const uint32_t *a, int) {
    int k = 0;
    void *sret = nullptr;
    if constexpr (is_sret<R>()) sret = reinterpret_cast<void *>(uintptr_t(a[k++]));
    C *self = reinterpret_cast<C *>(uintptr_t(a[k++]));
    auto args = word_args<P...>(a, k);
    return result<R>(sret, [&]() -> R { return std::apply([&](auto &&...x) -> R { return (self->*f)(std::forward<decltype(x)>(x)...); }, args); });
}
template <class... P, class R, class C> uint64_t adapt(R (C::*f)(P...) const, const uint32_t *a, int) {
    int k = 0;
    void *sret = nullptr;
    if constexpr (is_sret<R>()) sret = reinterpret_cast<void *>(uintptr_t(a[k++]));
    const C *self = reinterpret_cast<const C *>(uintptr_t(a[k++]));
    auto args = word_args<P...>(a, k);
    return result<R>(sret, [&]() -> R { return std::apply([&](auto &&...x) -> R { return (self->*f)(std::forward<decltype(x)>(x)...); }, args); });
}
// static member or free function
template <class... P, class R> uint64_t adapt(R (*f)(P...), const uint32_t *a, int) {
    int k = 0;
    void *sret = nullptr;
    if constexpr (is_sret<R>()) sret = reinterpret_cast<void *>(uintptr_t(a[k++]));
    auto args = word_args<P...>(a, k);
    return result<R>(sret, [&]() -> R { return std::apply([&](auto &&...x) -> R { return f(std::forward<decltype(x)>(x)...); }, args); });
}
// constructor (the ARM C++ ABI's constructors return this). Through a derived wrapper, so protected
// constructors work too (the game's own subclasses call them); the game stores its own vtable afterwards.
template <class C> struct Ctor : C {
    template <class... A> explicit Ctor(A &&...a) : C(std::forward<A>(a)...) {}
};
template <class C, class... P> uint64_t adapt_ctor(const uint32_t *a, int) {
    int k = 1;
    void *self = reinterpret_cast<void *>(uintptr_t(a[0]));
    auto args = word_args<P...>(a, k);
    std::apply([&](auto &&...x) { new (self) Ctor<C>(std::forward<decltype(x)>(x)...); }, args);
    return a[0];
}
// destructors: complete / base (return this, as on ARM), deleting
template <class C> uint64_t adapt_dtor(const uint32_t *a, int) {
    reinterpret_cast<C *>(uintptr_t(a[0]))->~C();
    return a[0];
}
template <class C> uint64_t adapt_delete(const uint32_t *a, int) {
    delete reinterpret_cast<C *>(uintptr_t(a[0]));
    return 0;
}

using Adapter = uint64_t (*)(const uint32_t *a, int n);
struct AdapterEntry { uint32_t addr; Adapter fn; const char *name; };

}  // namespace khux
