declare i32 @printf(i8*, ...)
declare i32 @scanf(i8*, ...)
declare i32 @gettimeofday(i8*, i8*)
declare double @sqrt(double)
declare i8* @malloc(i64)
declare i32 @rand()
declare void @srand(i32)
@fmt_int = private unnamed_addr constant [5 x i8] c"%ld\0A\00"
@fmt_float = private unnamed_addr constant [4 x i8] c"%f\0A\00"
@fmt_scan = private unnamed_addr constant [4 x i8] c"%ld\00"


define i64 @soma(i64 %arg_0, i64 %arg_1) {
entry:
  %a = alloca i64, align 8
  store i64 %arg_0, i64* %a, align 8
  %b = alloca i64, align 8
  store i64 %arg_1, i64* %b, align 8
  %reg_2 = load i64, i64* %a, align 8
  %reg_3 = load i64, i64* %b, align 8
  %tmp_1 = add nsw i64 %reg_2, %reg_3
  ret i64 %tmp_1
unreachable_4:
  ret i64 0
}
define i64 @media(i64 %arg_0, i64 %arg_1) {
entry:
  %a = alloca i64, align 8
  store i64 %arg_0, i64* %a, align 8
  %b = alloca i64, align 8
  store i64 %arg_1, i64* %b, align 8
  %reg_7 = load i64, i64* %a, align 8
  %reg_8 = load i64, i64* %b, align 8
  %tmp_6 = add nsw i64 %reg_7, %reg_8
  %tmp_5 = sdiv i64 %tmp_6, 2
  ret i64 %tmp_5
unreachable_10:
  ret i64 0
}
define i32 @main() {
entry:
  %st_tv_11 = alloca [16 x i8], align 8
  %st_tp_11 = getelementptr [16 x i8], [16 x i8]* %st_tv_11, i32 0, i32 0
  call i32 @gettimeofday(i8* %st_tp_11, i8* null)
  %st_up_11 = getelementptr i8, i8* %st_tp_11, i32 8
  %st_up6_11 = bitcast i8* %st_up_11 to i64*
  %st_uv_11 = load i64, i64* %st_up6_11
  %seed_11 = trunc i64 %st_uv_11 to i32
  call void @srand(i32 %seed_11)
  %x = alloca i64, align 8
  store i64 10, i64* %x, align 8
  %reg_14 = load i64, i64* %x, align 8
  %call_13 = call i64 @soma(i64 %reg_14, i64 5)
  %y = alloca i64, align 8
  store i64 %call_13, i64* %y, align 8
  %reg_16 = load i64, i64* %y, align 8
  %pf_17 = getelementptr [5 x i8], [5 x i8]* @fmt_int, i32 0, i32 0
  call i32 (i8*, ...) @printf(i8* %pf_17, i64 %reg_16)
  %bt_18 = mul nsw i64 5, 8
  %mr_18 = call i8* @malloc(i64 %bt_18)
  %mi_18 = ptrtoint i8* %mr_18 to i64
  %arr = alloca i64, align 8
  store i64 %mi_18, i64* %arr, align 8
  %reg_21 = load i64, i64* %y, align 8
  %ai_22 = load i64, i64* %arr, align 8
  %ap_22 = inttoptr i64 %ai_22 to i64*
  %ep_22 = getelementptr i64, i64* %ap_22, i64 0
  store i64 %reg_21, i64* %ep_22, align 8
  %ai_25 = load i64, i64* %arr, align 8
  %ap_25 = inttoptr i64 %ai_25 to i64*
  %ep_25 = getelementptr i64, i64* %ap_25, i64 0
  %ev_25 = load i64, i64* %ep_25, align 8
  %tmp_24 = srem i64 %ev_25, 4
  %ai_28 = load i64, i64* %arr, align 8
  %ap_28 = inttoptr i64 %ai_28 to i64*
  %ep_28 = getelementptr i64, i64* %ap_28, i64 1
  store i64 %tmp_24, i64* %ep_28, align 8
  %ai_31 = load i64, i64* %arr, align 8
  %ap_31 = inttoptr i64 %ai_31 to i64*
  %ep_31 = getelementptr i64, i64* %ap_31, i64 1
  %ev_31 = load i64, i64* %ep_31, align 8
  %cmp_30 = icmp sgt i64 %ev_31, 1
  br i1 %cmp_30, label %it_29, label %ie_29
it_29:
  %ai_34 = load i64, i64* %arr, align 8
  %ap_34 = inttoptr i64 %ai_34 to i64*
  %ep_34 = getelementptr i64, i64* %ap_34, i64 1
  %ev_34 = load i64, i64* %ep_34, align 8
  %pf_36 = getelementptr [5 x i8], [5 x i8]* @fmt_int, i32 0, i32 0
  call i32 (i8*, ...) @printf(i8* %pf_36, i64 %ev_34)
  br label %if_end_29
ie_29:
  %pf_38 = getelementptr [5 x i8], [5 x i8]* @fmt_int, i32 0, i32 0
  call i32 (i8*, ...) @printf(i8* %pf_38, i64 0)
  br label %if_end_29
if_end_29:
  %i = alloca i64, align 8
  store i64 0, i64* %i, align 8
  br label %c_40
c_40:
  %reg_42 = load i64, i64* %i, align 8
  %cmp_41 = icmp slt i64 %reg_42, 3
  br i1 %cmp_41, label %bt_40, label %be_40
bt_40:
  %reg_44 = load i64, i64* %i, align 8
  %pf_45 = getelementptr [5 x i8], [5 x i8]* @fmt_int, i32 0, i32 0
  call i32 (i8*, ...) @printf(i8* %pf_45, i64 %reg_44)
  %reg_47 = load i64, i64* %i, align 8
  %tmp_46 = add nsw i64 %reg_47, 1
  store i64 %tmp_46, i64* %i, align 8
  br label %c_40
be_40:
  %sq_49 = call double @sqrt(double 2.0)
  %raiz = alloca double, align 8
  store double %sq_49, double* %raiz, align 8
  %reg_51 = load double, double* %raiz, align 8
  %pf_52 = getelementptr [4 x i8], [4 x i8]* @fmt_float, i32 0, i32 0
  call i32 (i8*, ...) @printf(i8* %pf_52, double %reg_51)
  %call_53 = call i64 @media(i64 10, i64 3)
  %m = alloca i64, align 8
  store i64 %call_53, i64* %m, align 8
  %reg_56 = load i64, i64* %m, align 8
  %pf_57 = getelementptr [5 x i8], [5 x i8]* @fmt_int, i32 0, i32 0
  call i32 (i8*, ...) @printf(i8* %pf_57, i64 %reg_56)
  %cast_59 = trunc i64 0 to i32
  ret i32 %cast_59
unreachable_60:
  ret i32 0
}